import json
import re
from pathlib import Path
from xml.etree import ElementTree

import yaml
from tableaudocumentapi import Workbook

ROOT = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((ROOT / 'parity/report_spec.yaml').read_text())['entries']


def test_tableau_workbooks():
    paths = sorted((ROOT / 'consumers/tableau').glob('*.twb'))
    assert len(paths) == 3
    for path in paths:
        workbook = Workbook(str(path))
        assert workbook.datasources
        tree = ElementTree.parse(path)
        assert tree.find('.//relation').attrib['type'] == 'text'
        worksheets = tree.findall('.//worksheet')
        assert len(worksheets) == 3
        assert {zone.attrib['name'] for zone in tree.findall('.//dashboard/zones/zone')} == {sheet.attrib['name'] for sheet in worksheets}
        calculations = tree.findall("./datasources/datasource[@name='Reporting']/column/calculation")
        assert len(calculations) >= 3
        formulas = ' '.join(calc.attrib['formula'] for calc in calculations)
        assert 'ZN(' in formulas and 'IIF(' in formulas and '{FIXED' in formulas
        assert tree.find("./datasources/datasource[@name='Parameters']") is not None
        for relation in tree.findall('.//relation'):
            sql = relation.text
            if 'TOP (' in sql:
                assert 'ORDER BY' in sql
        if path.stem == 'Regional Sales':
            assert len(tree.findall('.//relation')) >= 2
        if path.stem == 'Retail Channels':
            sql = tree.find('.//relation').text
            assert 'DATE_TRUNC(' in sql and 'NVL(' in sql and '::date' in sql
        for element in tree.findall('.//worksheet') + tree.findall('.//dashboard'):
            assert any(e['source_file'] == str(path.relative_to(ROOT)) and e.get('name') == element.attrib['name'] for e in SPEC)


def test_powerbi_measures_and_cards():
    projects = list((ROOT / 'consumers/powerbi').glob('*.pbip'))
    assert len(projects) == 2
    for project in projects:
        base = project.with_suffix('')
        model = Path(str(base) + '.SemanticModel')
        for name in ['database', 'model', 'expressions', 'relationships']:
            assert (model / f'definition/{name}.tmdl').exists()
        measure_names = set()
        for table in (model / 'definition/tables').glob('*.tmdl'):
            names = re.findall(r"\tmeasure '([^']+)' =", table.read_text())
            measure_names.update(names)
            for name in names:
                assert any(e['kind'] == 'measure' and e.get('name') == name and e['source_file'] == str(table.relative_to(ROOT)) for e in SPEC)
        report_path = Path(str(base) + '.Report/report.json')
        report = json.loads(report_path.read_text())
        visuals = [visual for section in report['sections'] for visual in section['visualContainers']]
        assert len(visuals) == (11 if project.stem == 'Sales Performance' else 5)
        for visual in visuals:
            config = json.loads(visual['config'])
            name = config['singleVisual']['prototypeQuery']['Select'][0]['Measure']['Property']
            assert name in measure_names
            assert any(e.get('visual_id') == config['name'] and e['source_file'] == str(report_path.relative_to(ROOT)) for e in SPEC)


def test_model_expansion():
    model = ROOT / 'consumers/powerbi'
    sale = (model / 'Sales Performance.SemanticModel/definition/tables/Sale.tmdl').read_text()
    assert "column 'Sales Band' = IF(" in sale
    holding = (model / 'Order Fulfilment.SemanticModel/definition/tables/Stock Holding.tmdl').read_text()
    assert "partition 'Stock Holding' = m" in holding
    assert 'FROM Fact.[Stock Holding]' in holding
    assert len(re.findall(r"\tmeasure '([^']+)' =", holding)) == 2


def test_month_start_is_derived():
    date = (ROOT / 'consumers/powerbi/Sales Performance.SemanticModel/definition/tables/Date.tmdl').read_text()
    assert 'Table.AddColumn(Data, "Beginning of Month", each Date.StartOfMonth([Date]), type date)' in date
    assert 'Table.SelectColumns(WithMonth,' in date
    sql = next(entry['sql'] for entry in SPEC if entry['id'] == 'visual_sales_by_month')
    assert 'DATEFROMPARTS(d.[Calendar Year],d.[Calendar Month Number],1)' in sql
    assert 'd.[Beginning of Month]' not in sql


def test_spec_integrity():
    ids = [e['id'] for e in SPEC]
    assert len(ids) == len(set(ids))
    for entry in SPEC:
        assert re.fullmatch('[a-z0-9_]+', entry['id'])
        assert (ROOT / entry['source_file']).is_file()
        assert entry['sql'].startswith(('SELECT ', 'WITH '))
        assert entry['source'] in ('mssql', 'redshift')
        assert entry['grain'] and isinstance(entry['keys'], list)
        assert entry['numeric_tolerance']['absolute'] >= 0
    notebook = json.loads((ROOT / 'consumers/notebooks/monthly_sales.ipynb').read_text())
    assert notebook['nbformat'] == 4
