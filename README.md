# idx-bei

![neo4j-network-analysis](neo4j-network-analysis.png)

## Overview
**idx-bei** is a Node.js application designed to facilitate the easy download of data from the Indonesia Stock Exchange (IDX) / Bursa Efek Indonesia (BEI). This tool allows users to list available API endpoints from the IDX website and export the retrieved data in either JSON or CSV formats.

### Purpose
The primary purpose of this tool is educational. It provides a straightforward way to access financial data from IDX, helping users learn about financial data retrieval and manipulation. Users should review and comply with IDX's Terms of Service and Conditions (ToC) for proper usage.

## Features
- **API Listing**: Automatically fetch and list available API endpoints from the IDX website.
- **Data Export**: Export retrieved data in JSON or CSV format for easy analysis and reporting.

## Prerequisites
- Node.js (v14 or higher)
- npm (Node Package Manager)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ichsanulamal/idx-bei.git
   cd idx-bei
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

## Usage

To use the IDX/BEI data downloader, you can run the example scripts provided in the `examples` directory. These scripts demonstrate how to fetch and save different types of data from the IDX website.

### Fetching Company Profiles

This example fetches a list of all companies and then iterates through them to get detailed profile information for each. The data is saved incrementally to `data/companyDetailsByKodeEmiten.json`.

To run this example:
```bash
node examples/company-profiles.js
```

### Fetching Broker Search Data

This example fetches broker search data and saves it to `data/brokerSearch.json`.

To run this example:
```bash
node examples/broker-search.js
```

You can modify these examples or create your own scripts to download the specific data you need by importing and using the functions from the various modules in the project.

## Notes
- **Educational Use Only**: This tool is intended for educational purposes. Please review IDX's Terms of Service and Conditions for any restrictions on data usage.
- **Data Accuracy**: The accuracy and availability of data depend on the IDX website.

## Contributing
Contributions are welcome! If you find any issues or have suggestions for improvements, feel free to open an issue or submit a pull request.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

