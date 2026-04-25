# Slovak Energy Prices

This add-on exposes a small HTTP API for Slovak energy price data so Home Assistant can consume it with REST sensors, template sensors, or custom automations.

The main setup decision is the pricing model per utility:

- `household_fixed` for most domestic users with fixed or regulated end-user tariffs
- `spot_okte` for electricity users whose contracts follow Slovak day-ahead spot pricing
- `manual` for advanced cases where the user wants to provide custom supplier-specific data

For electricity and gas, `household_fixed` now supports two charge structures:

- `total`: enter one variable price and one monthly fixed fee from the contract
- `split`: enter commodity, distribution, taxes, and other parts separately; the add-on computes totals

## What is implemented

- Pricing mode selection for electricity, gas, and water
- Fixed-price household setup directly in add-on options
- Electricity day-ahead market prices from OKTE for spot-based contracts
- JSON API endpoints for Home Assistant
- Manual price file support for advanced supplier-specific setups

## Recommended Home Assistant process

1. Decide the pricing mode for each utility in the add-on options.
2. For household customers, keep `household_fixed` and enter the tariff values from the contract or invoice.
   Choose `total` if the contract only gives you one combined number, or `split` if you want invoice-style components.
3. For electricity contracts tied to spot prices, switch electricity to `spot_okte`.
4. For custom commercial or mixed tariffs, use `manual` and provide `custom_prices.json`.

This keeps Home Assistant sensor setup simple: your REST sensor can read one effective price endpoint regardless of whether the user is on fixed or spot pricing.

## Why only electricity is automatic right now

Electricity has an official documented API from OKTE:

- `GET https://isot.okte.sk/api/v1/dam/results?deliveryDayFrom=YYYY-MM-DD&deliveryDayTo=YYYY-MM-DD`

Gas and water do not currently have a similarly clean official public API confirmed in this repository:

- Gas pricing for Slovak households is published through ÚRSO decisions and calculator pages, but those sources are regulator-driven and not yet normalized here
- Water pricing is local-operator specific and published via ÚRSO decisions or municipality/operator price confirmations, so it is not one national live tariff feed

## Endpoints

- `/health`
- `/api/v1/prices/electricity/day-ahead?date_from=2026-04-25&date_to=2026-04-26`
- `/api/v1/prices/custom`
- `/api/v1/presets`
- `/api/v1/prices/effective`
- `/api/v1/prices/snapshot`

## Add-on options

Important options:

- `electricity_pricing_mode`: `household_fixed`, `spot_okte`, `manual`
- `gas_pricing_mode`: `household_fixed`, `manual`
- `water_pricing_mode`: `household_fixed`, `manual`
- `electricity_preset_id`: optional bundled provider tariff preset id
- `gas_preset_id`: optional bundled provider tariff preset id
- `water_preset_id`: reserved for future water-operator presets
- `electricity_charge_structure`: `total` or `split`
- `gas_charge_structure`: `total` or `split`

For household-fixed pricing, the add-on options hold the values used by Home Assistant:

- `electricity_fixed_price_eur_per_kwh`
- `electricity_fixed_monthly_fee_eur`
- `electricity_commodity_price_eur_per_kwh`
- `electricity_distribution_price_eur_per_kwh`
- `electricity_taxes_price_eur_per_kwh`
- `electricity_other_price_eur_per_kwh`
- `electricity_supplier_fixed_monthly_fee_eur`
- `electricity_distribution_fixed_monthly_fee_eur`
- `electricity_tax_fixed_monthly_fee_eur`
- `electricity_other_fixed_monthly_fee_eur`
- `gas_fixed_price_eur_per_kwh`
- `gas_fixed_monthly_fee_eur`
- `gas_commodity_price_eur_per_kwh`
- `gas_distribution_price_eur_per_kwh`
- `gas_taxes_price_eur_per_kwh`
- `gas_other_price_eur_per_kwh`
- `gas_supplier_fixed_monthly_fee_eur`
- `gas_distribution_fixed_monthly_fee_eur`
- `gas_tax_fixed_monthly_fee_eur`
- `gas_other_fixed_monthly_fee_eur`
- `water_supply_price_eur_per_m3`
- `water_wastewater_price_eur_per_m3`
- `water_fixed_monthly_fee_eur`

Water is exposed as separate `vodne` and `stocne` prices, plus a combined total for convenience.

## Provider presets

The add-on includes bundled household presets so users do not need to transcribe common tariffs manually.

Current preset coverage:

- Electricity: selected 2026 household tariffs from SPP and Energetika Slovensko / product line ZSE
- Gas: selected 2026 household tariffs from SPP
- Water: no bundled presets yet because water pricing is operator-specific by locality

List available preset ids:

- `GET /api/v1/presets`

Example option values:

- `electricity_preset_id: spp_regulated_2026_dd1`
- `electricity_preset_id: zse_regulated_2026_dd2`
- `gas_preset_id: spp_regulated_2026_d2`

If a preset id is set for a `household_fixed` utility, the preset overrides the manually entered fixed price fields for that utility.
Current electricity presets mostly reflect supplier tariff parts, while gas SPP presets already include separate supplier and distribution components.

## Manual pricing file

Create `custom_prices.json` in the add-on data folder. Inside the container it is read from `/data/custom_prices.json`.

Example:

```json
{
  "gas": {
    "source": "manual",
    "charge_structure": "split",
    "unit": "EUR/kWh",
    "supplier": "Custom SME gas contract",
    "commodity_price_eur_per_kwh": 0.038,
    "distribution_price_eur_per_kwh": 0.014,
    "taxes_price_eur_per_kwh": 0.002,
    "other_price_eur_per_kwh": 0.0,
    "supplier_fixed_monthly_fee_eur": 3.0,
    "distribution_fixed_monthly_fee_eur": 1.5,
    "tax_fixed_monthly_fee_eur": 0.0,
    "other_fixed_monthly_fee_eur": 0.0
  },
  "electricity": {
    "source": "manual",
    "charge_structure": "total",
    "unit": "EUR/kWh",
    "price": 0.143,
    "fixed_monthly_fee_eur": 6.5,
    "supplier": "Custom SME electricity contract"
  },
  "water": {
    "source": "manual",
    "unit": "EUR/m3",
    "water_supply_price": 1.25,
    "wastewater_price": 1.18,
    "water_supply_fixed_monthly_fee_eur": 0.4,
    "wastewater_fixed_monthly_fee_eur": 0.4,
    "operator_fixed_monthly_fee_eur": 0.2,
    "operator": "Bratislavska vodarenska spolocnost"
  }
}
```

For `electricity` and `gas`, manual mode now supports the same two structures as add-on options:

- `charge_structure: "total"` with `price` and `fixed_monthly_fee_eur`
- `charge_structure: "split"` with separate commodity, distribution, taxes, other, and fixed monthly components

For `water`, manual mode now supports separate fixed monthly components:

- `water_supply_fixed_monthly_fee_eur`
- `wastewater_fixed_monthly_fee_eur`
- `operator_fixed_monthly_fee_eur`

If only the older `fixed_monthly_fee_eur` is provided for water, it is treated as an operator-level fixed fee for backward compatibility.

## Example Home Assistant REST sensors

```yaml
rest:
  - resource: http://YOUR_ADDON_HOST:8099/api/v1/prices/effective
    scan_interval: 900
    sensor:
      - name: Slovak Electricity Effective Price
        value_template: "{{ value_json.prices.electricity.current_price }}"
        unit_of_measurement: "{{ value_json.prices.electricity.unit }}"
      - name: Slovak Gas Effective Price
        value_template: "{{ value_json.prices.gas.current_price }}"
        unit_of_measurement: "{{ value_json.prices.gas.unit }}"
      - name: Slovak Electricity Fixed Monthly Total
        value_template: "{{ value_json.prices.electricity.fixed_monthly_fee_eur }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Electricity Supplier Fixed Monthly
        value_template: "{{ value_json.prices.electricity.components.fixed_monthly.supplier_eur | default(value_json.prices.electricity.components.fixed_monthly.total_eur) }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Electricity Distribution Fixed Monthly
        value_template: "{{ value_json.prices.electricity.components.fixed_monthly.distribution_eur | default(0) }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Gas Fixed Monthly Total
        value_template: "{{ value_json.prices.gas.fixed_monthly_fee_eur }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Gas Supplier Fixed Monthly
        value_template: "{{ value_json.prices.gas.components.fixed_monthly.supplier_eur | default(value_json.prices.gas.components.fixed_monthly.total_eur) }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Gas Distribution Fixed Monthly
        value_template: "{{ value_json.prices.gas.components.fixed_monthly.distribution_eur | default(0) }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Water Effective Price
        value_template: "{{ value_json.prices.water.combined.current_price }}"
        unit_of_measurement: "{{ value_json.prices.water.combined.unit }}"
      - name: Slovak Vodne Price
        value_template: "{{ value_json.prices.water.vodne.current_price }}"
        unit_of_measurement: "{{ value_json.prices.water.vodne.unit }}"
      - name: Slovak Stocne Price
        value_template: "{{ value_json.prices.water.stocne.current_price }}"
        unit_of_measurement: "{{ value_json.prices.water.stocne.unit }}"
      - name: Slovak Water Fixed Monthly Total
        value_template: "{{ value_json.prices.water.combined.fixed_monthly_fee_eur }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Vodne Fixed Monthly
        value_template: "{{ value_json.prices.water.vodne.fixed_monthly_fee_eur }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Stocne Fixed Monthly
        value_template: "{{ value_json.prices.water.stocne.fixed_monthly_fee_eur }}"
        unit_of_measurement: "EUR/month"
      - name: Slovak Water Operator Fixed Monthly
        value_template: "{{ value_json.prices.water.components.fixed_monthly.operator_eur }}"
        unit_of_measurement: "EUR/month"
```

## Example Home Assistant Template Sensors For Daily Proration

```yaml
template:
  - sensor:
      - name: Slovak Electricity Fixed Daily
        unit_of_measurement: "EUR/day"
        state: >
          {% set monthly = states('sensor.slovak_electricity_fixed_monthly_total') | float(0) %}
          {% set month = now().month %}
          {% set year = now().year %}
          {% set leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0) %}
          {% set days = 29 if month == 2 and leap else 28 if month == 2 else 30 if month in [4, 6, 9, 11] else 31 %}
          {{ (monthly / days) | round(4) }}

      - name: Slovak Gas Fixed Daily
        unit_of_measurement: "EUR/day"
        state: >
          {% set monthly = states('sensor.slovak_gas_fixed_monthly_total') | float(0) %}
          {% set month = now().month %}
          {% set year = now().year %}
          {% set leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0) %}
          {% set days = 29 if month == 2 and leap else 28 if month == 2 else 30 if month in [4, 6, 9, 11] else 31 %}
          {{ (monthly / days) | round(4) }}

      - name: Slovak Water Fixed Daily
        unit_of_measurement: "EUR/day"
        state: >
          {% set monthly = states('sensor.slovak_water_fixed_monthly_total') | float(0) %}
          {% set month = now().month %}
          {% set year = now().year %}
          {% set leap = year % 400 == 0 or (year % 4 == 0 and year % 100 != 0) %}
          {% set days = 29 if month == 2 and leap else 28 if month == 2 else 30 if month in [4, 6, 9, 11] else 31 %}
          {{ (monthly / days) | round(4) }}

      - name: Slovak Electricity Daily Cost Per kWh Plus Fixed Share
        unit_of_measurement: "EUR"
        state: >
          {% set variable_price = states('sensor.slovak_electricity_effective_price') | float(0) %}
          {% set fixed_daily = states('sensor.slovak_electricity_fixed_daily') | float(0) %}
          {% set consumption_kwh = states('sensor.daily_electricity_usage_kwh') | float(0) %}
          {{ ((variable_price * consumption_kwh) + fixed_daily) | round(4) }}
```

This example assumes the REST sensors above already exist and that you have a daily usage sensor such as `sensor.daily_electricity_usage_kwh`.

## Notes

- OKTE now publishes 15-minute MTU market periods, not just hourly blocks
- Spot prices are relevant mainly for users on spot-linked contracts, not for typical domestic fixed-tariff users
- Household users still need to enter the real invoiced fixed tariff values from their supplier/operator
- End-user calculation in Home Assistant may still need distribution fees, taxes, and fixed fees if the user wants invoice-grade precision
