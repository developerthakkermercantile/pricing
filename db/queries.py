"""
db/queries.py — SQL queries for slab and item data.
All queries use :param style (SQLAlchemy text() compatible).
No inline -- comments inside SELECT — they cause tokenisation issues with text().
"""

SLAB_QUERY = """
SELECT
    item_price.item_code,
    item_price.price_list_rate,
    item_tax.item_tax_template,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 1), '|', -1)  AS market_place,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 2), '|', -1)  AS shipping,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 3), '|', -1)  AS shipping_level,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 4), '|', -1)  AS category,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 5), '|', -1)  AS area,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 6), '|', -1)  AS charger_type,
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 7), '|', -1)  AS bucket,
    CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 9),  '|', -1) AS DECIMAL(10,3)) AS lower_slab,
    CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 10), '|', -1) AS DECIMAL(10,3)) AS higher_slab,
    MAX(item_price.valid_from) AS latest_valid_from
FROM `tabItem Price` item_price
JOIN `tabItem` item ON item.name = item_price.item_code
LEFT JOIN `tabItem Tax` item_tax ON item_tax.parent = item_price.item_code
WHERE item.item_group = 'Ecommerce Charges'
  AND item.disabled   = 0
  AND item_price.price_list = 'ECom Charges'
GROUP BY item_price.item_code
HAVING market_place    = :market_place
  AND shipping         = :shipping
  AND shipping_level   = :shipping_level
  AND area             = :area
"""

DISTINCT_SHIPPING_LEVELS_QUERY = """
SELECT DISTINCT
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 3), '|', -1) AS shipping_level
FROM `tabItem Price` item_price
JOIN `tabItem` item ON item.name = item_price.item_code
WHERE item.item_group = 'Ecommerce Charges'
  AND item.disabled   = 0
  AND item_price.price_list = 'ECom Charges'
ORDER BY shipping_level
"""

DISTINCT_AREAS_QUERY = """
SELECT DISTINCT
    SUBSTRING_INDEX(SUBSTRING_INDEX(item_price.item_code, '|', 5), '|', -1) AS area
FROM `tabItem Price` item_price
JOIN `tabItem` item ON item.name = item_price.item_code
WHERE item.item_group = 'Ecommerce Charges'
  AND item.disabled   = 0
  AND item_price.price_list = 'ECom Charges'
ORDER BY area
"""

ITEM_QUERY = """
SELECT
    i.name                          AS item_code,
    i.item_name,
    COALESCE(i.valuation_rate, 0)   AS placeholder_cost,
    COALESCE(i.weight_per_unit, 0)  AS weight_per_unit,
    item_group                    AS amazon_category,
    it.item_tax_template
FROM `tabItem` i
LEFT JOIN `tabItem Tax` it
    ON  it.parent = i.name         -- Fixed: Joined on i.name instead of ib.item_code
    AND it.parenttype = 'Item'
    AND it.item_tax_template LIKE '%GST' -- Cleaned up the extra %
WHERE item_group != 'Ecommerce Charges'
  AND disabled = 0
ORDER BY item_name
"""

# Inside db/queries.py

ITEM_DESCENDANTS_QUERY = """
SELECT child.name AS descendant_group
FROM `tabItem Group` child
WHERE child.lft <= (
    SELECT p.lft 
    FROM `tabItem` i
    JOIN `tabItem Group` p ON p.name = i.item_group
    WHERE i.name = :item_code
)
AND child.rgt >= (
    SELECT p.rgt 
    FROM `tabItem` i
    JOIN `tabItem Group` p ON p.name = i.item_group
    WHERE i.name = :item_code
);
"""

ITEMS_MERGED_WITH_ECOM_CHARGES_QUERY = """
WITH ecom_charges AS (
    SELECT
        ec.item_code,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 1),  '|', -1))  AS market_place,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 2),  '|', -1))  AS shipping,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 3),  '|', -1))  AS shipping_level,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 4),  '|', -1))  AS category,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 5),  '|', -1))  AS shipping_area,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 6),  '|', -1))  AS charge_type,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 7),  '|', -1))  AS charge_uom,
        TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 8),  '|', -1))  AS additional_field,
        CAST(TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 9),  '|', -1)) AS DECIMAL(10,2))  AS ls,
        CAST(TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 10), '|', -1)) AS DECIMAL(10,2))  AS hs,
        ecom_ip.price_list_rate                                                   AS rate
    FROM `tabItem` ec
    INNER JOIN `tabItem Price` ecom_ip
        ON  ecom_ip.item_code  = ec.item_code
        AND ecom_ip.price_list = 'Ecom Charges'
        AND ecom_ip.valid_from = (
            SELECT MAX(ecom_ip2.valid_from)
            FROM `tabItem Price` ecom_ip2
            WHERE ecom_ip2.item_code  = ec.item_code
              AND ecom_ip2.price_list = 'Ecom Charges'
        )
    WHERE ec.item_group = 'Ecommerce Charges'
      AND ec.disabled   = 0
      AND TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 1), '|', -1)) = :market_place
      AND TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 2), '|', -1)) = :shipping
      AND TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 3), '|', -1)) = :shipping_level
      AND TRIM(SUBSTRING_INDEX(SUBSTRING_INDEX(ec.item_name, '|', 5), '|', -1)) = :area
),

item_base AS (
    SELECT
        i.item_code,
        i.item_name,
        i.item_group,
        i.pack_length,
        i.pack_height,
        i.pack_width,
        i.pack_weight,
        i.weight_per_unit,
        i.brand,
        CASE
            WHEN i.item_group IN (
                SELECT ig.item_group_name
                FROM `tabItem Group` ig
                INNER JOIN `tabItem Group` parent_ig
                    ON parent_ig.item_group_name = 'Website Group 07'
                WHERE ig.lft >= parent_ig.lft
                  AND ig.rgt <= parent_ig.rgt
            )
            THEN COALESCE((
                SELECT IF(pbi.qty > 1, pbi.qty, 1)
                FROM `tabProduct Bundle` pb
                INNER JOIN `tabProduct Bundle Item` pbi
                    ON pbi.parent = pb.name
                WHERE pb.new_item_code = i.item_code
                  AND pb.disabled      = 0
                LIMIT 1
            ), 1)
            ELSE 1
        END                                                 AS qty,
        (i.pack_length * i.pack_height * i.pack_width / 5000 * 1000)
                                                            AS volumetric_weight,
        GREATEST(
            i.pack_weight,
            (i.pack_length * i.pack_height * i.pack_width / 5000 * 1000)
        )                                                   AS chargeable_weight
    FROM `tabItem` i
    WHERE i.disabled = 0
      AND i.brand    IS NOT NULL
      AND i.brand    != ''
      AND i.item_code = "Nature's Blend Almond Mamra Selected 500 G Jar"
)

SELECT
    ib.item_code,
    ib.item_name,
    ib.item_group,
    ecom.buyer_child_id                         AS buyer_asin_id,
    ecom.seller_child_id                        AS seller_sku_id,
    ib.pack_length,
    ib.pack_height,
    ib.pack_width,
    ib.pack_weight,
    ib.weight_per_unit,
    ib.qty,
    ib.volumetric_weight,
    ib.chargeable_weight,
    mrp_ip.price_list_rate                      AS mrp,
    res_ip.price_list_rate                      AS reseller_rate,
    it.item_tax_template,
    mrp_ip.price_list_rate  * ib.qty            AS total_mrp,
    res_ip.price_list_rate  * ib.qty            AS total_reseller_rate,
    courier.rate                                AS courier_fee

FROM item_base ib

INNER JOIN `tabECom ID` ecom
    ON  ecom.parent     = ib.item_code
    AND ecom.parenttype = 'Item'
    AND ecom.ecom       = 'Amazon India FBA'

LEFT JOIN `tabItem Price` mrp_ip
    ON  mrp_ip.item_code  = ib.item_code
    AND mrp_ip.price_list = 'MRP Incl Tax'
    AND mrp_ip.valid_from = (
        SELECT MAX(mrp_ip2.valid_from)
        FROM `tabItem Price` mrp_ip2
        WHERE mrp_ip2.item_code  = ib.item_code
          AND mrp_ip2.price_list = 'MRP Incl Tax'
    )

LEFT JOIN `tabItem Price` res_ip
    ON  res_ip.item_code  = ib.item_code
    AND res_ip.price_list = 'Reseller Price Incl Tax'
    AND res_ip.valid_from = (
        SELECT MAX(res_ip2.valid_from)
        FROM `tabItem Price` res_ip2
        WHERE res_ip2.item_code  = ib.item_code
          AND res_ip2.price_list = 'Reseller Price Incl Tax'
    )

LEFT JOIN `tabItem Tax` it
    ON  it.parent     = ib.item_code
    AND it.parenttype = 'Item'
    AND it.item_tax_template LIKE '%%GST'

LEFT JOIN ecom_charges courier
    ON  courier.charge_type  = 'Courier Fees'
    AND ib.chargeable_weight >  courier.ls
    AND ib.chargeable_weight <= courier.hs
  """