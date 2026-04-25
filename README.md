# ha-slovak-energy-prices

Home Assistant add-on repository for Slovak energy price data.

Current implementation status:

- Pricing model first: household fixed tariffs or spot-linked pricing
- Bundled provider presets for selected common 2026 household tariffs
- Electricity: official OKTE day-ahead market API is scaffolded for spot users
- Gas: fixed household pricing is supported as input; automated tariff ingestion is still research
- Water: fixed local tariff input is supported as separate `vodne` and `stocne`; automated tariff ingestion is still research

Repository layout:

- `repository.yaml` defines the Home Assistant add-on repository
- `slovak_energy_prices/` contains the first add-on scaffold

The add-on currently exposes a small REST API so Home Assistant can consume Slovak prices through REST sensors and templates.
