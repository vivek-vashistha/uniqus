# Contract→606 Intelligence - Caching System

## 🎯 Overview

The caching system prevents duplicate file uploads, reuses vector stores, and caches LLM analysis results to optimize performance and reduce costs.

## 🔧 Key Features

### 1. **File Deduplication**
- **SHA-256 Hashing**: Files are identified by content hash, not filename
- **Automatic Detection**: Same files are detected regardless of filename changes
- **Cache Storage**: File metadata stored with hash, size, and upload timestamp

### 2. **Analysis Sessions**
- **Session Grouping**: Related documents grouped into analysis sessions
- **Vector Store Reuse**: Multiple files can share the same vector store
- **Session Management**: Track and manage analysis sessions over time

### 3. **LLM Analysis Caching**
- **Question-Level Caching**: Each ASC-606 question cached separately
- **File-Based Keys**: Cache keys include file hashes for accuracy
- **Expiration**: Cache expires after 24 hours for freshness

### 4. **Smart Vector Store Management**
- **Session-Based**: Vector stores created per session, not per file
- **File Addition**: New files added to existing vector stores
- **Cost Optimization**: Reduces OpenAI vector store creation costs

## 🏗️ Architecture

### Backend Components

#### Cache Manager (`backend/services/cache_manager.py`)
```python
class CacheManager:
    - files_db: Dict[str, FileMetadata]  # file_hash -> metadata
    - sessions_db: Dict[str, AnalysisSession]  # session_id -> session
    - analysis_cache: Dict[str, CachedAnalysis]  # cache_key -> analysis
```

#### File Metadata
```python
@dataclass
class FileMetadata:
    file_id: str
    filename: str
    file_hash: str
    file_size: int
    upload_timestamp: datetime
    vector_store_id: Optional[str]
```

#### Analysis Session
```python
@dataclass
class AnalysisSession:
    session_id: str
    session_name: str
    created_timestamp: datetime
    vector_store_id: str
    file_hashes: List[str]
    analysis_results: Dict[str, Any]
    last_updated: datetime
```

### Frontend Components

#### Session Manager (`frontend/src/components/SessionManager.js`)
- **Session List**: View all analysis sessions
- **Cache Statistics**: Monitor cache usage and performance
- **Session Details**: View files and analysis results per session
- **Cache Cleanup**: Manual cache cleanup functionality

#### Enhanced Upload (`frontend/src/components/DocumentUpload.js`)
- **Session Name Input**: Optional session naming
- **Cache Status Display**: Shows if files are cached or new
- **Smart Upload**: Automatically detects and reuses cached files

## 🚀 Usage

### 1. **File Upload with Caching**
```javascript
// Upload with session name
const formData = new FormData();
formData.append('file', file);
formData.append('session_name', 'Contract_Analysis_2024');
formData.append('reuse_existing', 'true');

const response = await axios.post('/upload', formData);
// Returns: { cached: true/false, session_id, file_hash }
```

### 2. **Session Management**
```javascript
// List all sessions
const sessions = await axios.get('/sessions');

// Get session details
const session = await axios.get(`/sessions/${sessionId}`);

// Add file to existing session
const result = await axios.post(`/sessions/${sessionId}/add-file`, formData);
```

### 3. **Cache Statistics**
```javascript
// Get cache statistics
const stats = await axios.get('/cache/stats');
// Returns: { total_files, total_sessions, total_analyses, cache_size_mb }

// Clean up expired cache
await axios.post('/cache/cleanup', { max_age_hours: 168 });
```

## 📊 Cache Performance

### Benefits
- **Cost Reduction**: Avoid re-uploading same files to OpenAI
- **Speed Improvement**: Cached analyses return instantly
- **Resource Optimization**: Reuse vector stores for related documents
- **Storage Efficiency**: File deduplication reduces storage needs

### Cache Statistics
```json
{
  "total_files": 25,
  "total_sessions": 8,
  "total_analyses": 120,
  "cache_size_mb": 15.2
}
```

## 🔄 Cache Lifecycle

### 1. **File Upload**
```
File Upload → Calculate Hash → Check Cache → 
If Cached: Return Existing Analysis
If New: Upload to OpenAI → Create/Reuse Vector Store → Cache Metadata
```

### 2. **Analysis Processing**
```
Question Analysis → Check Analysis Cache →
If Cached: Return Cached Result
If New: Run LLM Analysis → Cache Result → Return Analysis
```

### 3. **Session Management**
```
Session Creation → Group Files → Create Vector Store →
Add Files to Vector Store → Cache Session Metadata
```

## 🛠️ Configuration

### Environment Variables
```env
# OpenAI Configuration
DIRECT_OPENAI_API_KEY=your_api_key
VECTOR_STORE_ID=optional_existing_vector_store

# Cache Configuration (optional)
CACHE_DIR=cache
CACHE_EXPIRY_HOURS=24
```

### Cache Directory Structure
```
cache/
├── files.json          # File metadata cache
├── sessions.json       # Session cache
├── analyses.json       # Analysis results cache
└── files/              # File storage (if needed)
```

## 🔍 Monitoring & Maintenance

### Cache Statistics Dashboard
- **File Count**: Number of cached files
- **Session Count**: Number of analysis sessions
- **Analysis Count**: Number of cached analyses
- **Cache Size**: Total cache size in MB

### Cache Cleanup
- **Automatic**: Expired analyses cleaned up on access
- **Manual**: Cleanup endpoint for maintenance
- **Configurable**: Expiry time configurable (default: 7 days)

### Performance Monitoring
```python
# Get cache hit rates
cache_stats = cache_manager.get_cache_stats()
hit_rate = cache_stats['cache_hits'] / cache_stats['total_requests']
```

## 🚨 Troubleshooting

### Common Issues

1. **Cache Not Working**
   - Check file permissions on cache directory
   - Verify cache directory exists and is writable
   - Check for disk space issues

2. **Duplicate Files Still Uploading**
   - Verify file content is identical (not just filename)
   - Check hash calculation is working correctly
   - Ensure cache is being saved properly

3. **Analysis Not Cached**
   - Check cache key generation
   - Verify file hashes are consistent
   - Check cache expiry settings

### Debug Commands
```bash
# Check cache directory
ls -la cache/

# View cache files
cat cache/files.json
cat cache/sessions.json
cat cache/analyses.json

# Check cache size
du -sh cache/
```

## 📈 Performance Optimization

### Best Practices

1. **Session Naming**: Use descriptive session names for better organization
2. **File Grouping**: Group related documents in the same session
3. **Cache Cleanup**: Regularly clean up expired cache entries
4. **Monitoring**: Monitor cache hit rates and adjust expiry times

### Optimization Tips

1. **Vector Store Reuse**: Group related documents to reuse vector stores
2. **Analysis Caching**: Cache frequently asked questions
3. **File Deduplication**: Avoid uploading identical files
4. **Session Management**: Use sessions to organize related analyses

## 🔒 Security Considerations

### Data Protection
- **File Hashing**: Files identified by hash, not content
- **Cache Encryption**: Consider encrypting sensitive cache data
- **Access Control**: Implement proper access controls for cache data

### Privacy
- **PII Handling**: Ensure cached data doesn't contain sensitive information
- **Data Retention**: Implement proper data retention policies
- **Cache Cleanup**: Regular cleanup of sensitive cached data

## 🎯 Future Enhancements

### Planned Features
1. **Distributed Caching**: Redis/Memcached for multi-instance deployments
2. **Cache Compression**: Compress cached data to reduce storage
3. **Smart Preloading**: Preload common analyses
4. **Cache Analytics**: Detailed cache performance analytics
5. **Auto-Cleanup**: Automatic cache cleanup based on usage patterns

### Advanced Features
1. **Cache Invalidation**: Smart cache invalidation strategies
2. **Cache Warming**: Pre-populate cache with common analyses
3. **Performance Metrics**: Detailed cache performance monitoring
4. **Cache Optimization**: Automatic cache optimization algorithms

## 📞 Support

For issues with the caching system:

1. **Check Logs**: Review application logs for cache-related errors
2. **Verify Configuration**: Ensure cache directory and permissions are correct
3. **Monitor Performance**: Use cache statistics to identify issues
4. **Clean Cache**: Try cleaning cache if experiencing issues

The caching system significantly improves performance and reduces costs while maintaining the same user experience!
