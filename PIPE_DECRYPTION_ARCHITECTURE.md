# ClearKey解密管道架构文档

## 概述

基于您的正确指出，FFmpeg本身不具备ClearKey解密的能力。我们已经重新设计了解密架构，使用外部工具进行ClearKey解密，然后通过管道将解密后的流传递给FFmpeg进行HLS转换。

## 架构设计

### 🔄 管道流程

```
[MPEG-DASH流] → [外部解密器] → [管道] → [FFmpeg] → [HLS输出]
      ↓              ↓           ↓         ↓          ↓
   加密的MPD    yt-dlp/自定义   stdout   stdin    playlist.m3u8
   + ClearKey     解密工具      流传输    接收      + segments
```

### 🛠️ 技术实现

#### 1. 外部解密器 (`decrypt_dash.py`)

**管道模式新功能:**
- `--output-format pipe`: 输出到stdout而非文件
- `--pipe-format ts`: 输出MPEG-TS格式供FFmpeg处理
- 支持yt-dlp的ClearKey解密能力

**使用方式:**
```bash
python decrypt_dash.py [MPD_URL] --license-key [KEY_ID:KEY] --output-format pipe --pipe-format ts
```

#### 2. 管道连接 (`app.py`)

**新增方法:**
- `_create_hls_with_decryption_pipe()`: 创建解密管道
- `_monitor_decryption_pipe()`: 监控双进程状态
- `_restart_decryption_pipe()`: 重启管道流程

**进程管理:**
```python
# 启动解密进程
decrypt_process = subprocess.Popen(decrypt_cmd, stdout=subprocess.PIPE, ...)

# 启动FFmpeg进程，连接解密输出
ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdin=decrypt_process.stdout, ...)

# 关闭解密进程的stdout避免管道阻塞
decrypt_process.stdout.close()
```

## 🎯 优势对比

### 原有方案问题:
- ❌ FFmpeg的`-decryption_key`参数支持有限
- ❌ 需要临时文件存储，增加I/O开销
- ❌ 两步处理：解密→转换，效率低

### 新管道方案优势:
- ✅ 使用yt-dlp的成熟ClearKey解密能力
- ✅ 流式处理，无需临时文件
- ✅ 实时解密+转换，效率高
- ✅ 更好的错误处理和监控

## 🔧 详细配置

### 解密命令构建:
```python
decrypt_cmd = [
    'python', 'decrypt_dash.py',
    mpd_url,
    '--license-key', license_key,
    '--output-format', 'pipe',
    '--pipe-format', 'ts'
]
```

### FFmpeg管道命令:
```python
ffmpeg_cmd = [
    'ffmpeg', '-y',
    '-f', 'mpegts',        # 输入格式
    '-i', 'pipe:0',        # 从stdin读取
    '-c:v', 'libx264',     # 视频编码
    '-c:a', 'aac',         # 音频编码
    '-f', 'hls',           # 输出HLS格式
    # ... HLS参数
    'playlist.m3u8'
]
```

## 🔍 监控与错误处理

### 双进程监控:
- 同时监控解密进程和FFmpeg进程
- 任一进程异常都会触发重启逻辑
- 智能错误分析和重试策略

### 错误处理增强:
```python
def _analyze_ffmpeg_error(output, return_code):
    # 分析网络错误、格式错误、权限错误等
    # 返回人类可读的错误描述

def _should_retry_error(error_analysis, current_restarts):
    # 根据错误类型决定是否重试
    # 403/404不重试，网络错误限制重试次数

def _get_retry_delay(error_analysis, retry_count):
    # 网络错误使用指数退避策略
    # 其他错误使用固定延迟
```

## 🧪 测试验证

运行测试脚本验证功能:
```bash
python test_pipe_decryption.py
```

测试覆盖:
- ✅ 脚本语法检查
- ✅ 命令构建验证
- ✅ FFmpeg可用性检查
- ✅ 流连接性测试
- ✅ 错误分析功能

## 🚀 使用示例

### 启动加密流:
```python
# 通过API或Web界面添加流
{
    "name": "加密频道",
    "url": "https://example.com/stream.mpd",
    "license_key": "key_id_hex:key_hex",
    "license_type": "clearkey"
}
```

### 自动处理流程:
1. 检测到ClearKey许可证
2. 启动解密管道模式
3. yt-dlp解密DASH流
4. 管道传输到FFmpeg
5. FFmpeg生成HLS输出
6. 客户端播放HLS流

## 🔧 故障排除

### 常见问题:

1. **yt-dlp不可用**
   - 确保安装: `pip install yt-dlp`
   - 检查版本: `yt-dlp --version`

2. **管道连接失败**
   - 检查进程间通信
   - 查看错误日志分析

3. **ClearKey格式错误**
   - 确保格式: `key_id:key`
   - 检查hex编码正确性

### 日志示例:
```
2025-08-30 21:41:17 - INFO - 检测到ClearKey加密流，使用外部解密器: stream_1
2025-08-30 21:41:17 - INFO - 启动解密管道: python decrypt_dash.py... | ffmpeg...
2025-08-30 21:41:20 - INFO - 解密管道已成功启动 (stream_id: stream_1)
```

## 📈 性能优化

### 管道优势:
- 🚀 流式处理，减少延迟
- 💾 节省磁盘I/O和存储空间
- ⚡ 并行解密和转换处理
- 🔄 实时错误检测和恢复

### 监控指标:
- 进程状态 (running/error/stopped)
- 重启次数统计
- 输出文件生成状态
- 错误类型分析

这个新架构真正解决了ClearKey解密的核心问题，提供了专业级的流媒体处理能力。
