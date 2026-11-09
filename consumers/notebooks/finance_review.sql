SELECT DATEPART(year,[Invoice Date Key]) AS sales_year, DATEPART(month,[Invoice Date Key]) AS sales_month, SUM([Total Excluding Tax]) AS sales, SUM([Profit]) AS profit FROM Fact.Sale GROUP BY DATEPART(year,[Invoice Date Key]), DATEPART(month,[Invoice Date Key]) ORDER BY sales_year, sales_month;

SELECT TOP (20) [Customer Key], SUM([Profit]) AS profit FROM Fact.Sale GROUP BY [Customer Key] ORDER BY profit DESC, [Customer Key];
