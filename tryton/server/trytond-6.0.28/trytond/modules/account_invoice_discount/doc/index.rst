Account Invoice Discount Module
###############################

Tryton module to add discounts on invoice lines.

From the "Discount" and the "Gross unit price", the "Unit price" field is calculated as:

Unit price = Gross unit price * (1 - Discount)

By default the number of decimal places of "Gross unit price" and "Discount" is 4. The number of decimal places of "Unit Price" is the sum of both, by default 8.
To change the number of decimal places of "Gross unit price" and / or "Discount", for example 3 and 2 respectively, you can define the following variables in trytond configuration file:

unit_price_digits = 3
discount_digits = 2
