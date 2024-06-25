# Peridio EVK CLI

This is a command-line tool for initializing the Peridio EVK.

## Installation

```bash
pip install -e .
pip install -r requirements.txt
```

## Usage

### Configure the EVK and CLI to use a specified organization

```bash
peridio-evk configure --organization-name <ORGANIZATION_NAME> --organization-prn <ORGANIZARION_PRN> --api-key <API_KEY>
```

- Configure the CLI config for the organization
- Create evk.json config and store evk configured values
  - profile
  - organization_name
  - organization_prn
- Ensure the CLI is installed and functional
- Check the CLI credentials for the evk profile

### Create a product in the org

```bash
peridio-evk create-product --name <PRODUCT_NAME>
```

- Create the product in Peridio Cloud if it does not exist
- Create cohorts for the product
  - release
  - reelease-debug
  - daily-release
  - daily-debug
- Create Intermediate CA Certificate for each cohort
- Enable JITP for each signing certificate to adopt into that product cohort
- Create firmware signing keys for the each cohort
- Registers signing key pairs with the CLI config
