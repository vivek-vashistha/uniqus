# Contract→606 Intelligence & Autofill

A comprehensive full-stack application for ASC-606 compliance automation with AI-powered contract analysis. Features both a modern web interface and command-line tools for document processing, clause analysis, and evidence generation.

## Features

### 🎯 Core Capabilities
- **AI-Powered Analysis**: GPT-4 powered contract analysis with ASC-606 compliance focus
- **Document Processing**: Upload and process PDF, Word, Excel, and other document formats
- **Clause Detection**: Automatic identification of contract clauses and terms
- **Evidence Generation**: Create auditable evidence binders with highlighted clauses
- **Human-in-the-Loop**: Expert review and override capabilities
- **Export Ready**: Generate CSV, JSON, and PDF outputs for portal integration

### 🌐 Web Interface
- **Modern React Frontend**: Intuitive drag-and-drop document upload
- **Real-time Analysis**: Live ASC-606 question analysis with confidence scoring
- **Review Console**: Side-by-side clause review and override interface
- **Analytics Dashboard**: Track processing metrics and success rates
- **Evidence Binder**: Generated evidence with highlighted clauses and citations

### 🖥️ Command Line Interface
- **Document Upload**: Upload documents to OpenAI vector stores
- **QnA Operations**: Ask questions about uploaded documents
- **Vector Store Management**: Create, list, and clear vector stores
- **Batch Processing**: Process multiple documents efficiently

## Architecture

### 🏗️ System Overview

The application consists of three main components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend│    │  FastAPI Backend│    │  OpenAI Vector  │
│   (Port 3000)   │◄──►│   (Port 8000)   │◄──►│     Store       │
│                 │    │                 │    │                 │
│ • Document Upload│    │ • Document Proc.│    │ • Document Index│
│ • Review Console│    │ • Clause Engine │    │ • Semantic Search│
│ • Analytics     │    │ • LLM Analysis  │    │ • File Search   │
│ • Evidence Binder│   │ • API Endpoints │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 🔧 Backend (FastAPI)
- **Document Processing**: PDF/Word ingestion with OCR and section detection
- **Clause Engine**: ASC-606 focused clause taxonomy and detection
- **Analysis Engine**: AI-powered question answering with confidence scoring
- **Review Interface**: Human-in-the-loop validation and override
- **Export System**: Evidence binder generation and portal-ready exports
- **Vector Store Integration**: OpenAI vector store management and querying

### 🎨 Frontend (React)
- **Document Upload**: Drag-and-drop interface for contract documents
- **Review Console**: Side-by-side clause review and override interface
- **Evidence Binder**: Generated evidence with highlighted clauses
- **Analytics Dashboard**: Processing metrics and success criteria tracking
- **Template Manager**: ASC-606 question template management
- **Session Manager**: Project and session management

### 🤖 AI Integration
- **OpenAI GPT-4**: Advanced language model for contract analysis
- **Vector Store**: Semantic search and document retrieval
- **File Search**: Context-aware document analysis
- **Confidence Scoring**: Reliability indicators for each analysis

## Installation

### Prerequisites

- **Python 3.8+** for backend services
- **Node.js 16+** for frontend development
- **OpenAI API key** with access to GPT-4 and vector store features

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

2. **Backend Setup**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install Python dependencies
   pip install -r requirements.txt
   ```

3. **Frontend Setup**
   ```bash
   # Install Node.js dependencies
   cd frontend
   npm install
   cd ..
   ```

4. **Environment Configuration**
   ```bash
   # Create environment file
   cp env.example .env
   ```

5. **Configure environment variables**
   Edit `.env` file with your OpenAI API key:
   ```env
   DIRECT_OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4o
   VECTOR_STORE_ID=vs_your_vector_store_id_here
   ```

## Quick Start

### 🌐 Web Interface (Recommended)

1. **Start the Backend Server**
   ```bash
   ./start_backend.sh
   ```
   The backend will be available at `http://localhost:8000`

2. **Start the Frontend Development Server**
   ```bash
   ./start_frontend.sh
   ```
   The frontend will be available at `http://localhost:3000`

3. **Open your browser** and navigate to `http://localhost:3000`

### 🖥️ Command Line Interface

After setup, you can test the CLI with the demo script:

```bash
python demo.py
```

This will show you all available commands and their help information.

## Usage

The application provides two interfaces: a modern web interface and a command-line interface.

### 🌐 Web Interface Usage

The web interface provides an intuitive way to manage contracts and ASC-606 compliance:

1. **Document Upload**: Drag and drop contract documents onto the upload area
2. **Automatic Analysis**: The system automatically analyzes documents for ASC-606 compliance
3. **Review Console**: Review AI-generated answers and provide expert overrides
4. **Evidence Binder**: Generate auditable evidence with highlighted clauses
5. **Analytics Dashboard**: Track processing metrics and success rates

### 🖥️ Command Line Interface

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
├── backend/                  # FastAPI Backend
│   ├── main.py              # Main FastAPI application
│   ├── services/            # Backend services
│   │   ├── cache_manager.py # Cache management
│   │   ├── clause_engine.py # Clause detection engine
│   │   ├── document_processor.py # Document processing
│   │   └── markdown_analyzer.py # Markdown analysis
│   ├── cache/               # Cache storage
│   ├── output/              # Generated outputs
│   └── uploads/             # Uploaded documents
├── frontend/                 # React Frontend
│   ├── src/
│   │   ├── components/      # React components
│   │   │   ├── DocumentUpload.js
│   │   │   ├── DocumentReview.js
│   │   │   ├── EvidenceBinder.js
│   │   │   ├── Analytics.js
│   │   │   ├── SessionManager.js
│   │   │   ├── MarkdownAnalyzer.js
│   │   │   └── TemplateManager.js
│   │   ├── App.js           # Main React app
│   │   └── index.js         # React entry point
│   ├── public/              # Static assets
│   └── package.json         # Node.js dependencies
├── data/                     # Sample documents
│   ├── Contracts/           # Contract samples
│   └── ASC-606-Doc/         # ASC-606 documentation
├── questionset/             # ASC-606 question templates
├── tools/                    # Legacy tools (deprecated)
├── cli.py                    # Command-line interface
├── requirements.txt          # Python dependencies
├── start_backend.sh          # Backend startup script
├── start_frontend.sh         # Frontend startup script
└── README.md                 # This file
```

## API Documentation

The backend provides a comprehensive REST API for document processing and ASC-606 analysis. The API documentation is automatically generated and available at `http://localhost:8000/docs` when the backend is running.

### 🔗 Key Endpoints

#### Document Management
- `POST /upload` - Upload documents for analysis
- `GET /documents` - List all documents
- `GET /documents/{document_id}` - Get document details
- `POST /documents/{document_id}/review` - Submit reviewer overrides
- `POST /documents/{document_id}/reanalyze` - Re-analyze specific questions

#### Project Management
- `GET /projects` - List all projects
- `GET /projects/{project_id}` - Get project details
- `POST /projects/{project_id}/add-file` - Add file to project
- `POST /projects/{project_id}/ingest` - Ingest project files
- `POST /projects/{project_id}/analyze` - Analyze project

#### Analysis & Chat
- `GET /projects/{project_id}/analyze/stream` - Stream analysis results
- `GET /projects/{project_id}/chat/stream` - Stream chat responses
- `POST /projects/{project_id}/chat` - Send chat message
- `GET /projects/{project_id}/steps` - Get analysis steps

#### Evidence & Export
- `POST /documents/{document_id}/evidence-binder` - Generate evidence binder
- `GET /evidence-binders/{binder_id}` - Get evidence binder
- `GET /download/{binder_id}/{format}` - Download evidence in various formats

#### Templates & Configuration
- `GET /templates` - List all templates
- `GET /templates/{step}` - Get specific template
- `PUT /templates/{step}` - Update template
- `POST /templates/{step}/reset` - Reset template to default

#### System
- `GET /health` - Health check
- `GET /analytics` - System analytics
- `GET /cache/stats` - Cache statistics
- `POST /cache/cleanup` - Clean up cache

### 📊 Response Formats

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}
```

Error responses:
```json
{
  "success": false,
  "error": "Error message",
  "details": { ... }
}
```

## Examples

### 🌐 Web Interface Workflow

1. **Start the application:**
   ```bash
   # Terminal 1: Start backend
   ./start_backend.sh
   
   # Terminal 2: Start frontend
   ./start_frontend.sh
   ```

2. **Upload documents:**
   - Open `http://localhost:3000` in your browser
   - Drag and drop contract documents onto the upload area
   - Documents are automatically processed and analyzed

3. **Review analysis:**
   - Navigate to the Review Console
   - Review AI-generated ASC-606 answers
   - Provide expert overrides where needed

4. **Generate evidence:**
   - Click "Generate Evidence Binder"
   - Download PDF, CSV, or JSON formats
   - Share with stakeholders

### 🖥️ CLI Workflow

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

#### Backend Issues

1. **API Key Missing**
   ```
   ❌ DIRECT_OPENAI_API_KEY is missing in .env
   ```
   **Solution:** Add your OpenAI API key to the `.env` file.

2. **Backend Won't Start**
   ```
   ❌ ModuleNotFoundError: No module named 'fastapi'
   ```
   **Solution:** Install dependencies: `pip install -r requirements.txt`

3. **Port Already in Use**
   ```
   ❌ Address already in use: 8000
   ```
   **Solution:** Kill existing process or use different port: `uvicorn backend.main:app --port 8001`

#### Frontend Issues

4. **Frontend Won't Start**
   ```
   ❌ Module not found: Can't resolve 'react'
   ```
   **Solution:** Install dependencies: `cd frontend && npm install`

5. **Port Already in Use**
   ```
   ❌ Port 3000 is already in use
   ```
   **Solution:** Kill existing process or use different port: `PORT=3001 npm start`

#### CLI Issues

6. **Vector Store ID Missing**
   ```
   ❌ VECTOR_STORE_ID missing in .env
   ```
   **Solution:** Either set VECTOR_STORE_ID in `.env` or use `--vector-store-id` flag.

7. **No Files Found**
   ```
   ⚠️ No files found in 'folder' with extensions {'.pdf', '.txt', '.md', '.docx', '.csv', '.pptx'}
   ```
   **Solution:** Ensure your folder contains supported file types.

8. **Upload Failures**
   ```
   ❌ Failed for file.pdf: [error message]
   ```
   **Solution:** Check file format, size, and API quota.

### Getting Help

#### Web Interface
- **API Documentation**: Visit `http://localhost:8000/docs` for interactive API documentation
- **Health Check**: Visit `http://localhost:8000/health` to verify backend status
- **Analytics**: Visit `http://localhost:8000/analytics` for system metrics

#### Command Line Interface
Run the CLI with `--help` for detailed usage information:

```bash
python cli.py --help
python cli.py upload --help
python cli.py qna --help
python cli.py clear --help
python cli.py list --help
```

#### Debug Mode
```bash
# Enable debug logging for backend
export LOG_LEVEL=DEBUG
./start_backend.sh

# Enable debug logging for frontend
REACT_APP_DEBUG=true npm start
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
