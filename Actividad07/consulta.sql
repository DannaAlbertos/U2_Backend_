-- 1. Consultar las cuentas existentes
SELECT *
FROM accounts;

-- 2. Consultar los conceptos existentes
SELECT *
FROM concepts;

-- 3. Consultar las relaciones entre cuentas y conceptos
SELECT *
FROM account_concepts;

-- 4. Consultar la estructura de la tabla concepts
PRAGMA table_info(concepts);

-- 5. Consultar la estructura de la tabla account_concepts
PRAGMA table_info(account_concepts);

-- 6. Consultar la estructura de la tabla transactions
PRAGMA table_info(transactions);

SELECT * FROM users;

