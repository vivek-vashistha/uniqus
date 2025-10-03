# OpenAI Vector Store CLI Tool

A comprehensive command-line interface for managing OpenAI vector stores and performing QnA operations on document collections. This tool is specifically designed for contract review and ASC 606 compliance analysis.

## Features

- **Document Upload**: Upload documents to OpenAI vector stores with support for multiple file formats
- **QnA Operations**: Ask questions about uploaded documents with structured responses
- **Vector Store Management**: Create, list, and clear vector stores
- **Logging**: Comprehensive logging of all operations
- **Flexible Configuration**: Environment-based configuration with fallback options

## Installation

### Prerequisites

- Python 3.8 or higher
- OpenAI API key with access to GPT-4 and vector store features

### Quick Setup

**Option 1: Automated Setup (Recommended)**
```bash
# Clone or download the project
git clone <repository-url>
cd uniqus

# Run automated setup
python setup.py
```

**Option 2: Manual Setup**

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd uniqus
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**
   ```bash
   cp env.example .env
   ```

4. **Configure environment variables**
   Edit `.env` file with your OpenAI API key:
   ```env
   DIRECT_OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4o
   VECTOR_STORE_ID=vs_your_vector_store_id_here
   ```

## Quick Start

After setup, you can test the CLI with the demo script:

```bash
python demo.py
```

This will show you all available commands and their help information.

## Usage

The CLI tool provides four main commands: `upload`, `qna`, `clear`, and `list`.

### Upload Documents

Upload documents from a folder to a vector store:

```bash
python cli.py upload ./data --name "my_knowledge_base"
```

**Options:**
- `folder`: Path to folder containing documents to upload
- `--name`: Name for the vector store (default: "knowledge_base")
- `--use-existing`: Use existing vector store from VECTOR_STORE_ID env var

**Supported file formats:**
- PDF (.pdf)
- Text (.txt)
- Markdown (.md)
- Word documents (.docx)
- CSV (.csv)
- PowerPoint (.pptx)

**Example:**
```bash
# Upload documents from data folder
python cli.py upload ./data

# Upload with custom name
python cli.py upload ./contracts --name "contract_review"

# Upload to existing vector store
python cli.py upload ./new_docs --use-existing
```

### Ask Questions (QnA)

Ask questions about the uploaded documents:

```bash
python cli.py qna "Is the contract approved and are the parties committed to their obligations?"
```

**Example questions:**
```bash
# ASC 606 compliance questions
python cli.py qna "Can the payment terms for the goods and services be identified (ASC 606-10-25-1(c))?"

# Contract analysis
python cli.py qna "Are there any contracts entered into at or near the same time with the same customer?"

# Performance obligations
python cli.py qna "Goods or services promised in the contracts are a single performance obligation?"
```

### List Files in Vector Store

List all files currently in a vector store:

```bash
python cli.py list
```

**Options:**
- `--vector-store-id`: Specific vector store ID to list (uses VECTOR_STORE_ID env var if not provided)

### Clear Vector Store

Delete a vector store and all its contents:

```bash
python cli.py clear --vector-store-id vs_abc123
```

**Options:**
- `--vector-store-id`: Vector store ID to delete (uses VECTOR_STORE_ID env var if not provided)

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DIRECT_OPENAI_API_KEY` | Your OpenAI API key | Yes | - |
| `OPENAI_MODEL` | OpenAI model to use | No | `gpt-4o` |
| `VECTOR_STORE_ID` | Default vector store ID | No | - |

### Logging

All operations are logged to `upload_log.txt` with timestamps and details:
```
2025-01-03T13:40:46.537686 | Action: UPLOAD | File: contract.pdf | VectorStoreID: vs_abc123
2025-01-03T13:45:12.123456 | Action: DELETE | VectorStoreID: vs_abc123
```

## Project Structure

```
uniqus/
├── cli.py                    # Main CLI application
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── .env                      # Environment configuration
├── upload_log.txt           # Operation logs
├── data/                     # Sample documents
│   ├── Contract 1/
│   │   ├── Contract 1 file 2 2.pdf
│   │   └── Contract 1 file 3 2.pdf
│   └── revenue-from-contracts-with-customers-updated-220124.pdf
└── tools/                    # Legacy tools (deprecated)
    ├── clear_vector_store.py
    └── upload_file_to_vector_store.py
```

## Examples

### Complete Workflow

1. **Upload documents:**
   ```bash
   python cli.py upload ./data --name "contract_analysis"
   ```

2. **List uploaded files:**
   ```bash
   python cli.py list
   ```

3. **Ask questions:**
   ```bash
   python cli.py qna "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?"
   ```

4. **Clear when done:**
   ```bash
   python cli.py clear --vector-store-id vs_your_id_here
   ```

### ASC 606 Compliance Checklist

The tool is specifically designed for ASC 606 compliance analysis. Here are common questions you can ask:

```bash
# Contract identification
python cli.py qna "Is the contract approved and are the parties committed to their obligations (ASC 606-10-25-1(a))?"

# Payment terms
python cli.py qna "Can the payment terms for the goods and services be identified (ASC 606-10-25-1(c))?"

# Commercial substance
python cli.py qna "Has the contract commercial substance (ASC 606-10-25-1(d))?"

# Related contracts
python cli.py qna "Are there any contracts entered into at or near the same time (rebuttable presumption 3 months) with the same customer or related parties of the customer?"

# Performance obligations
python cli.py qna "Goods or services promised in the contracts (or some goods or services promised in each contract) are a single performance obligation in accordance with paragraphs 606-10-25-14 through 25-22?"
```

## Troubleshooting

### Common Issues

1. **API Key Missing**
   ```
   ❌ DIRECT_OPENAI_API_KEY is missing in .env
   ```
   **Solution:** Add your OpenAI API key to the `.env` file.

2. **Vector Store ID Missing**
   ```
   ❌ VECTOR_STORE_ID missing in .env
   ```
   **Solution:** Either set VECTOR_STORE_ID in `.env` or use `--vector-store-id` flag.

3. **No Files Found**
   ```
   ⚠️ No files found in 'folder' with extensions {'.pdf', '.txt', '.md', '.docx', '.csv', '.pptx'}
   ```
   **Solution:** Ensure your folder contains supported file types.

4. **Upload Failures**
   ```
   ❌ Failed for file.pdf: [error message]
   ```
   **Solution:** Check file format, size, and API quota.

### Getting Help

Run the CLI with `--help` for detailed usage information:

```bash
python cli.py --help
python cli.py upload --help
python cli.py qna --help
python cli.py clear --help
python cli.py list --help
```

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the OpenAI API documentation
3. Create an issue in the repository
