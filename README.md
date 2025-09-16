# Zoho Price Matcher

🚀 **Automated inventory price matching system** that keeps your Zoho Inventory prices current with real-time market data.

## Features

- 📊 **Google Sheets Integration** - Reads inventory data from spreadsheets
- 🔍 **AI-Powered Price Search** - Uses OpenAI GPT-4o to find current market prices
- 🎯 **Smart Item Matching** - Intelligent matching between sheets and Zoho Inventory
- ⚡ **Rate Limiting** - Respects API limits and handles large datasets
- 📝 **Comprehensive Logging** - Full audit trail of all operations
- 🚀 **Railway Ready** - One-click deployment to Railway

## How It Works

1. Reads inventory items from Google Sheets
2. Searches web for current market prices using AI
3. Matches items with Zoho Inventory using SKU, name, and brand
4. Updates Zoho with current market prices
5. Logs all operations for audit trail

## Current Data

- **760 inventory items** ready for processing
- **18 data columns** including Item Name, SKU, Brand, Estimated Value
- **Smart filtering** - skips already processed items
- **Batch processing** with rate limiting

## Deployment

Deploy to Railway with environment variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `ZOHO_TOKEN` - Zoho OAuth token
- `ZOHO_ORG_ID` - Zoho organization ID

## Tech Stack

- Python 3.11
- OpenAI GPT-4o
- Zoho Inventory API
- Google Sheets API
- Railway deployment
- Pandas for data processing
- Requests for API calls

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python app.py
```

## Environment Variables

Set these environment variables before running:

```bash
export OPENAI_API_KEY="your_openai_key_here"
export ZOHO_TOKEN="your_zoho_token_here"
export ZOHO_ORG_ID="your_org_id_here"
```

## Features in Detail

### Smart Item Matching
- **SKU Matching**: Exact SKU matches get highest priority
- **Name Similarity**: Word overlap scoring for item names
- **Brand Matching**: Brand consistency scoring
- **Confidence Threshold**: Only matches with 30+ confidence score

### Price Search
- **Multiple Sources**: Searches 3-5 different sources
- **Unit Conversion**: Handles per-piece, per-case, per-pack pricing
- **Average Calculation**: Calculates market average price
- **Confidence Scoring**: 0-100 confidence rating

### Rate Limiting
- **Zoho API Limits**: Respects 100 requests/minute limit
- **Automatic Delays**: Built-in delays between requests
- **Error Handling**: Comprehensive error recovery

### Logging
- **File Logging**: All operations logged to `price_matcher.log`
- **Console Output**: Real-time progress updates
- **Results Export**: JSON results file with timestamp
- **Error Tracking**: Detailed error reporting

## Results

The system generates detailed results including:
- Items processed
- Items matched with Zoho
- Items successfully updated
- Errors encountered
- Detailed operation logs

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues or questions, please open an issue on GitHub.
