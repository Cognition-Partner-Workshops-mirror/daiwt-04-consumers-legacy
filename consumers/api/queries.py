CUSTOMER = """SELECT [Customer Key] AS customer_key, COUNT(DISTINCT [WWI Invoice ID]) AS invoices,
SUM([Total Excluding Tax]) AS sales, SUM([Profit]) AS profit
FROM Fact.Sale WHERE [Customer Key] = ? GROUP BY [Customer Key]"""
MONTHLY = """SELECT DATEPART(month,[Invoice Date Key]) AS month,
SUM([Total Excluding Tax]) AS sales, SUM([Profit]) AS profit
FROM Fact.Sale WHERE [Invoice Date Key] >= DATEFROMPARTS(?,1,1)
AND [Invoice Date Key] < DATEFROMPARTS(?+1,1,1)
GROUP BY DATEPART(month,[Invoice Date Key]) ORDER BY month"""
TERRITORY = """SELECT c.[Sales Territory] AS territory, SUM(s.[Total Excluding Tax]) AS sales
FROM Fact.Sale s JOIN Dimension.City c ON s.[City Key]=c.[City Key]
WHERE DATEPART(year,s.[Invoice Date Key])=? GROUP BY c.[Sales Territory] ORDER BY territory"""
TOP_ITEMS = """SELECT TOP (?) s.[Stock Item Key] AS stock_item_key, i.[Stock Item] AS stock_item,
SUM(s.[Total Excluding Tax]) AS sales FROM Fact.Sale s
JOIN Dimension.[Stock Item] i ON s.[Stock Item Key]=i.[Stock Item Key]
GROUP BY s.[Stock Item Key],i.[Stock Item] ORDER BY sales DESC, stock_item_key"""
CUSTOMER_ORDERS = """SELECT TOP (?) [WWI Order ID] AS order_id, [Order Date Key] AS order_date,
SUM([Total Excluding Tax]) AS order_value, SUM([Quantity]) AS quantity,
SUM(CASE WHEN [Picked Date Key] IS NULL THEN 1 ELSE 0 END) AS unpicked_lines
FROM Fact.[Order] WHERE [Customer Key] = ?
GROUP BY [WWI Order ID], [Order Date Key]
ORDER BY order_date DESC, order_id DESC"""
