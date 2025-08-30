/**
 * MPD流媒体管理系统 - 主要JavaScript功能
 */

class StreamManager {
    constructor() {
        this.streams = [];
        this.updateInterval = null;
        this.init();
    }

    async init() {
        await this.loadStreams();
        this.checkHealth();
        this.bindEvents();
        this.startPeriodicUpdates();
    }

    bindEvents() {
        // 添加流表单
        const addForm = document.getElementById('add-stream-form');
        if (addForm) {
            addForm.addEventListener('submit', (e) => this.handleAddStream(e));
        }

        // 编辑流表单
        const editForm = document.getElementById('edit-stream-form');
        if (editForm) {
            editForm.addEventListener('submit', (e) => this.handleEditStream(e));
        }

        // 许可证类型变化事件
        const licenseType = document.getElementById('license-type');
        if (licenseType) {
            licenseType.addEventListener('change', () => this.toggleLicenseKeyInput(false));
        }

        const editLicenseType = document.getElementById('edit-license-type');
        if (editLicenseType) {
            editLicenseType.addEventListener('change', () => this.toggleLicenseKeyInput(true));
        }

        // 模态框外部点击关闭
        window.addEventListener('click', (e) => this.handleModalClick(e));
        
        // 键盘快捷键
        document.addEventListener('keydown', (e) => this.handleKeyDown(e));
    }

    startPeriodicUpdates() {
        // 每30秒检查健康状态
        setInterval(() => this.checkHealth(), 30000);
        
        // 每5秒更新流状态
        this.updateInterval = setInterval(() => this.updateStreamStatus(), 5000);
    }

    // 健康检查
    async checkHealth() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            const healthElement = document.getElementById('health-status');
            if (healthElement) {
                healthElement.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="fas fa-check-circle text-success"></i>
                            <strong>服务器运行正常</strong>
                        </div>
                        <div class="badge badge-success">${data.active_streams || 0} 活跃</div>
                    </div>
                    <small class="text-muted">最后更新: ${new Date().toLocaleString()}</small>
                `;
            }
        } catch (error) {
            const healthElement = document.getElementById('health-status');
            if (healthElement) {
                healthElement.innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-triangle"></i>
                        服务器连接失败: ${error.message}
                    </div>
                `;
            }
        }
    }

    // 加载流列表
    async loadStreams() {
        try {
            const response = await fetch('/streams');
            const data = await response.json();
            this.streams = data.streams || [];
            this.renderStreams();
            this.updateStats();
        } catch (error) {
            this.showError('加载流列表失败: ' + error.message);
        }
    }

    // 渲染流列表
    renderStreams() {
        const container = document.getElementById('streams-container');
        if (!container) return;

        if (this.streams.length === 0) {
            container.innerHTML = `
                <div class="text-center p-4">
                    <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                    <p class="text-muted">暂无流配置</p>
                    <small>请在左侧添加新的流配置</small>
                </div>
            `;
            return;
        }

        container.innerHTML = this.streams.map(stream => this.renderStreamCard(stream)).join('');
    }

    // 渲染单个流卡片
    renderStreamCard(stream) {
        const statusClass = this.getStatusClass(stream.status);
        const statusText = this.getStatusText(stream.status);
        const isRunning = stream.status === 'running';

        return `
            <div class="card mb-3 stream-card ${statusClass}" data-stream-id="${stream.id}">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-1">${this.escapeHtml(stream.name)}</h5>
                        <small class="text-muted">ID: ${stream.id}</small>
                    </div>
                    <span class="badge ${this.getStatusBadgeClass(stream.status)}">${statusText}</span>
                </div>
                
                <div class="card-body">
                    <div class="mb-2">
                        <strong>源地址:</strong> 
                        <code class="text-break">${this.escapeHtml(stream.url)}</code>
                    </div>
                    
                    <div class="mb-2">
                        <strong>类型:</strong> ${stream.manifest_type || 'MPD'}
                        ${stream.license_type ? `<span class="badge badge-info ml-1">${stream.license_type.toUpperCase()}</span>` : ''}
                        ${!stream.enabled ? '<span class="badge badge-warning ml-1">已禁用</span>' : ''}
                    </div>
                    
                    ${isRunning ? `
                        <div class="alert alert-success mb-2">
                            <strong>HLS播放地址:</strong><br>
                            <code class="user-select-all" onclick="this.select()" title="点击选择全部">
                                ${window.location.origin}${stream.hls_url}
                            </code>
                            <button class="btn btn-sm btn-outline-primary ml-2" onclick="streamManager.copyToClipboard('${window.location.origin}${stream.hls_url}')">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                    ` : ''}
                </div>
                
                <div class="card-footer d-flex justify-content-between flex-wrap">
                    <div class="btn-group mb-2">
                        ${isRunning ? 
                            `<button class="btn btn-warning btn-sm" onclick="streamManager.stopStream('${stream.id}')">
                                <i class="fas fa-stop"></i> 停止
                            </button>` :
                            `<button class="btn btn-success btn-sm" onclick="streamManager.startStream('${stream.id}')" 
                                    ${!stream.enabled ? 'disabled title="流已禁用"' : ''}>
                                <i class="fas fa-play"></i> 启动
                            </button>`
                        }
                        <button class="btn btn-primary btn-sm" onclick="streamManager.editStream('${stream.id}')">
                            <i class="fas fa-edit"></i> 编辑
                        </button>
                        <button class="btn btn-danger btn-sm" onclick="streamManager.deleteStream('${stream.id}')">
                            <i class="fas fa-trash"></i> 删除
                        </button>
                    </div>
                    
                    ${isRunning ? `
                        <button class="btn btn-info btn-sm mb-2" onclick="streamManager.testStream('${stream.id}')">
                            <i class="fas fa-play-circle"></i> 测试播放
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }

    // 更新统计信息
    updateStats() {
        const totalElement = document.getElementById('total-streams');
        const runningElement = document.getElementById('running-streams');
        
        if (totalElement) totalElement.textContent = this.streams.length;
        if (runningElement) {
            const runningCount = this.streams.filter(s => s.status === 'running').length;
            runningElement.textContent = runningCount;
        }
    }

    // 更新流状态
    async updateStreamStatus() {
        if (this.streams.length === 0) return;

        try {
            const statusPromises = this.streams.map(async (stream) => {
                try {
                    const response = await fetch(`/streams/${stream.id}/status`);
                    if (response.ok) {
                        return await response.json();
                    }
                } catch (error) {
                    console.warn(`Failed to get status for stream ${stream.id}:`, error);
                }
                return null;
            });

            const statuses = await Promise.all(statusPromises);
            let hasChanges = false;

            statuses.forEach((status, index) => {
                if (status && this.streams[index].status !== status.status) {
                    this.streams[index] = { ...this.streams[index], ...status };
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                this.renderStreams();
                this.updateStats();
            }
        } catch (error) {
            console.warn('Failed to update stream statuses:', error);
        }
    }

    // 添加流
    async handleAddStream(event) {
        event.preventDefault();
        
        const form = event.target;
        const submitBtn = form.querySelector('button[type="submit"]');
        const formData = new FormData(form);
        
        this.setLoading(submitBtn, true);
        
        const data = {
            name: formData.get('name'),
            url: formData.get('url'),
            license_type: formData.get('license_type') || undefined,
            license_key: formData.get('license_key') || undefined,
            manifest_type: 'mpd',
            enabled: formData.has('enabled')
        };

        try {
            const response = await fetch('/streams', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                this.showSuccess(`流添加成功！流ID: ${result.stream_id}`);
                form.reset();
                await this.loadStreams();
            } else {
                this.showError('添加失败: ' + result.error);
            }
        } catch (error) {
            this.showError('网络错误: ' + error.message);
        } finally {
            this.setLoading(submitBtn, false);
        }
    }

    // 编辑流
    async handleEditStream(event) {
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        const streamId = document.getElementById('edit-stream-id').value;
        
        const data = {
            name: formData.get('name'),
            url: formData.get('url'),
            license_type: formData.get('license_type') || undefined,
            license_key: formData.get('license_key') || undefined,
            enabled: formData.has('enabled')
        };

        try {
            const response = await fetch(`/streams/${streamId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                this.showSuccess(`流 ${streamId} 更新成功`);
                this.closeEditModal();
                await this.loadStreams();
            } else {
                this.showError('更新失败: ' + result.error);
            }
        } catch (error) {
            this.showError('更新失败: ' + error.message);
        }
    }

    // 启动流
    async startStream(streamId) {
        try {
            const response = await fetch(`/streams/${streamId}/start`, { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`流 ${streamId} 启动成功`);
                this.updateStreamInList(streamId, { status: 'starting' });
            } else {
                this.showError('启动失败: ' + result.error);
            }
        } catch (error) {
            this.showError('启动失败: ' + error.message);
        }
    }

    // 停止流
    async stopStream(streamId) {
        try {
            const response = await fetch(`/streams/${streamId}/stop`, { method: 'POST' });
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`流 ${streamId} 停止成功`);
                this.updateStreamInList(streamId, { status: 'stopped' });
            } else {
                this.showError('停止失败: ' + result.error);
            }
        } catch (error) {
            this.showError('停止失败: ' + error.message);
        }
    }

    // 删除流
    async deleteStream(streamId) {
        if (!confirm(`确定要删除流 ${streamId} 吗？此操作不可撤销。`)) return;
        
        try {
            const response = await fetch(`/streams/${streamId}`, { method: 'DELETE' });
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`流 ${streamId} 删除成功`);
                await this.loadStreams();
            } else {
                this.showError('删除失败: ' + result.error);
            }
        } catch (error) {
            this.showError('删除失败: ' + error.message);
        }
    }

    // 编辑流对话框
    editStream(streamId) {
        const stream = this.streams.find(s => s.id === streamId);
        if (!stream) return;

        document.getElementById('edit-stream-id').value = stream.id;
        document.getElementById('edit-stream-name').value = stream.name;
        document.getElementById('edit-stream-url').value = stream.url;
        document.getElementById('edit-license-type').value = stream.license_type || '';
        document.getElementById('edit-license-key').value = stream.license_key || '';
        document.getElementById('edit-stream-enabled').checked = stream.enabled !== false;
        
        this.toggleLicenseKeyInput(true);
        this.showEditModal();
    }

    // 测试播放
    testStream(streamId) {
        const stream = this.streams.find(s => s.id === streamId);
        if (!stream || stream.status !== 'running') return;
        
        const hlsUrl = `${window.location.origin}${stream.hls_url}`;
        
        // 尝试用VLC打开
        const vlcUrl = `vlc://${hlsUrl}`;
        window.open(vlcUrl, '_blank');
        
        // 显示播放地址
        this.showInfo(`
            <strong>HLS播放地址:</strong><br>
            <code>${hlsUrl}</code><br>
            <small>已尝试用VLC打开，也可复制地址到其他播放器</small>
        `);
    }

    // 复制到剪贴板
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showSuccess('地址已复制到剪贴板');
        } catch (error) {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                this.showSuccess('地址已复制到剪贴板');
            } catch (err) {
                this.showError('复制失败，请手动复制');
            } finally {
                document.body.removeChild(textArea);
            }
        }
    }

    // 工具方法
    updateStreamInList(streamId, updates) {
        const index = this.streams.findIndex(s => s.id === streamId);
        if (index !== -1) {
            this.streams[index] = { ...this.streams[index], ...updates };
            this.renderStreams();
            this.updateStats();
        }
    }

    toggleLicenseKeyInput(isEdit = false) {
        const licenseType = document.getElementById(isEdit ? 'edit-license-type' : 'license-type');
        const keyGroup = document.getElementById(isEdit ? 'edit-license-key-group' : 'license-key-group');
        
        if (licenseType && keyGroup) {
            keyGroup.style.display = licenseType.value === 'clearkey' ? 'block' : 'none';
        }
    }

    showEditModal() {
        const modal = document.getElementById('edit-modal');
        if (modal) modal.style.display = 'block';
    }

    closeEditModal() {
        const modal = document.getElementById('edit-modal');
        if (modal) modal.style.display = 'none';
    }

    handleModalClick(event) {
        const modal = document.getElementById('edit-modal');
        if (event.target === modal) {
            this.closeEditModal();
        }
    }

    handleKeyDown(event) {
        if (event.key === 'Escape') {
            this.closeEditModal();
        }
    }

    setLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.innerHTML = '<span class="spinner mr-1"></span>处理中...';
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || '提交';
        }
    }

    getStatusClass(status) {
        const classes = {
            'running': 'border-success',
            'stopped': 'border-danger',
            'starting': 'border-warning',
            'stopping': 'border-warning'
        };
        return classes[status] || '';
    }

    getStatusText(status) {
        const texts = {
            'running': '运行中',
            'stopped': '已停止',
            'starting': '启动中',
            'stopping': '停止中'
        };
        return texts[status] || status;
    }

    getStatusBadgeClass(status) {
        const classes = {
            'running': 'badge-success',
            'stopped': 'badge-danger',
            'starting': 'badge-warning',
            'stopping': 'badge-warning'
        };
        return classes[status] || 'badge-secondary';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showSuccess(message) {
        this.showAlert(message, 'success');
    }

    showError(message) {
        this.showAlert(message, 'danger');
    }

    showInfo(message) {
        this.showAlert(message, 'info');
    }

    showAlert(message, type) {
        const alertDiv = document.getElementById('status-message');
        if (!alertDiv) return;

        alertDiv.className = `alert alert-${type}`;
        alertDiv.innerHTML = message;
        alertDiv.style.display = 'block';
        
        setTimeout(() => {
            alertDiv.style.display = 'none';
        }, 5000);
    }
}

// 全局实例
let streamManager;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    streamManager = new StreamManager();
});
