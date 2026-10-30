-- Crear un concepto de egreso para la prueba B05.
-- Solo se inserta si todavía no existe.

INSERT INTO concepts (
    company_id,
    concept_type,
    name,
    short_description,
    long_description,
    is_active,
    created_at,
    updated_at
)
SELECT
    1,
    'EXPENSE',
    'Pago de servicios',
    'Concepto de prueba B05',
    'Concepto utilizado para validar transactionDate',
    1,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1
    FROM concepts
    WHERE company_id = 1
      AND concept_type = 'EXPENSE'
      AND name = 'Pago de servicios'
);

-- Asociar el concepto a la cuenta 1, si no existe la relación.

INSERT INTO account_concepts (
    account_id,
    concept_id,
    is_active,
    created_at
)
SELECT
    1,
    c.id,
    1,
    CURRENT_TIMESTAMP
FROM concepts AS c
WHERE c.company_id = 1
  AND c.concept_type = 'EXPENSE'
  AND c.name = 'Pago de servicios'
  AND NOT EXISTS (
      SELECT 1
      FROM account_concepts AS ac
      WHERE ac.account_id = 1
        AND ac.concept_id = c.id
  );

-- Verificar el concepto y su asociación.

SELECT
    c.id AS concept_id,
    c.name AS concept_name,
    c.concept_type,
    c.company_id,
    ac.account_id,
    ac.is_active AS association_active
FROM concepts AS c
JOIN account_concepts AS ac
    ON ac.concept_id = c.id
WHERE c.company_id = 1
  AND c.concept_type = 'EXPENSE'
  AND c.name = 'Pago de servicios'
  AND ac.account_id = 1;