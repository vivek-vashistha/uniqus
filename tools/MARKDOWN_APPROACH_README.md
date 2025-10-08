# ASC 606 Markdown-Based Analysis

This new approach uses markdown templates as direct prompts for ASC 606 analysis, providing more flexibility and comprehensive coverage than the previous structured approach.

## Key Features

- **Template-Based**: Uses markdown templates (`step1.md`, `step2.md`, etc.) as direct prompts
- **Progressive Context**: Each step includes outputs from previous steps as context
- **Flexible Output**: Generates filled markdown files for each step
- **Better Coverage**: Captures complex reasoning and detailed analysis

## Architecture

```
Contract Files → Vector Store → Markdown Templates → Filled Outputs
                     ↓
              Progressive Context Building
              (Step 1 → Step 1+2 → Step 1+2+3...)
```

## Usage

### 1. Ingest Contract Files

```bash
python asc606_markdown_filler.py ingest --contract_id C-001 --files "contract.pdf" "sow.docx"
```

### 2. Run Analysis

```bash
python asc606_markdown_filler.py analyze --contract_id C-001 --output_dir "./output/C-001"
```

### 3. Review Results

The analysis generates:
- `step1_filled.md` - Contract identification
- `step2_filled.md` - Performance obligations  
- `step3_filled.md` - Transaction price
- `step4_filled.md` - Price allocation
- `step5_filled.md` - Revenue recognition

## Context Management Strategy

### Progressive Context Building

Each step includes the complete output from all previous steps:

- **Step 1**: No context (first step)
- **Step 2**: Includes Step 1 results
- **Step 3**: Includes Step 1 + Step 2 results
- **Step 4**: Includes Step 1 + Step 2 + Step 3 results
- **Step 5**: Includes Step 1 + Step 2 + Step 3 + Step 4 results

### Benefits

1. **Comprehensive Analysis**: Each step has full context from previous analysis
2. **Consistency**: Later steps can reference and build upon earlier findings
3. **Flexibility**: Templates can be modified without code changes
4. **Auditability**: Full traceability of reasoning across all steps

## Template Structure

Each markdown template contains:

- **Instructions**: Clear guidance for the AI
- **Questions**: Specific ASC 606 questions to answer
- **Placeholders**: `{placeholder}` markers to be filled
- **Formatting**: Proper markdown structure for readability

Example placeholder:
```markdown
**Answer:** {Answer in Yes/No/Not Applicable/Unknown, along with rationale}
```

## Advantages Over Previous Approach

| Aspect | Previous (Structured) | New (Markdown) |
|--------|----------------------|----------------|
| **Flexibility** | Limited to predefined fields | Full natural language |
| **Coverage** | Basic heuristics + simple RAG | Comprehensive analysis |
| **Context** | No cross-step context | Progressive context building |
| **Output** | JSON/Excel only | Rich markdown with citations |
| **Maintenance** | Code changes needed | Template changes only |

## Error Handling

- **Template Loading**: Validates template existence
- **API Calls**: Handles OpenAI API errors gracefully
- **Context Building**: Skips missing previous steps
- **Output Validation**: Warns about short responses
- **File Operations**: Creates error files for failed steps

## Testing

Run the test script to validate the setup:

```bash
python test_markdown_approach.py
```

This tests:
- Template loading
- Context building
- Dependencies
- API key configuration

## Configuration

### Environment Variables

```bash
export DIRECT_OPENAI_API_KEY="sk-..."
```

### Model Selection

```bash
python asc606_markdown_filler.py analyze --model "gpt-4.1" --contract_id C-001
```

## Output Structure

```
output/
├── C-001/
│   ├── step1_filled.md
│   ├── step2_filled.md
│   ├── step3_filled.md
│   ├── step4_filled.md
│   └── step5_filled.md
```

Each filled markdown file contains:
- Complete ASC 606 analysis for that step
- Specific evidence and citations
- Proper formatting and structure
- All placeholders replaced with actual content

## Future Enhancements

1. **DeepAgents Integration**: Could use DeepAgents for more sophisticated context management
2. **Template Versioning**: Support for different template versions
3. **Validation Rules**: Automated validation of filled content
4. **Interactive Mode**: Step-by-step review and approval
5. **Export Options**: PDF, Word, or other formats

## Troubleshooting

### Common Issues

1. **Template Not Found**: Ensure `questionset/` directory exists with all step templates
2. **API Errors**: Check API key and model availability
3. **Short Responses**: May indicate insufficient contract content or API issues
4. **Context Issues**: Previous step files must exist for context building

### Debug Mode

Add verbose logging by modifying the script to include more detailed output during processing.
