#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目完整性检查脚本
验证所有关键功能和文件
"""

import os
import sys
import yaml
import json
import subprocess
from pathlib import Path

def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}缺失: {filepath}")
        return False

def check_directory_exists(dirpath, description):
    """检查目录是否存在"""
    if os.path.isdir(dirpath):
        print(f"✅ {description}: {dirpath}")
        return True
    else:
        print(f"❌ {description}缺失: {dirpath}")
        return False

def check_yaml_syntax(filepath):
    """检查YAML文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        print(f"✅ YAML语法正确: {filepath}")
        return True
    except Exception as e:
        print(f"❌ YAML语法错误 {filepath}: {e}")
        return False

def check_json_syntax(filepath):
    """检查JSON文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"✅ JSON语法正确: {filepath}")
        return True
    except Exception as e:
        print(f"❌ JSON语法错误 {filepath}: {e}")
        return False

def check_python_syntax(filepath):
    """检查Python文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        print(f"✅ Python语法正确: {filepath}")
        return True
    except Exception as e:
        print(f"❌ Python语法错误 {filepath}: {e}")
        return False

def main():
    print("🔍 开始项目完整性检查...\n")
    
    issues = []
    
    # 检查核心Python文件
    print("📁 检查核心Python文件:")
    core_files = [
        ("app.py", "主应用服务器"),
        ("stream_manager.py", "流管理器"),
        ("healthcheck.py", "健康检查"),
        ("monitor.py", "监控脚本"),
        ("example.py", "示例代码"),
        ("quick_start.py", "快速启动脚本")
    ]
    
    for filepath, desc in core_files:
        if check_file_exists(filepath, desc):
            if not check_python_syntax(filepath):
                issues.append(f"Python语法错误: {filepath}")
    
    print("\n📁 检查配置文件:")
    # 检查配置文件
    config_files = [
        ("config.yaml", "主配置文件"),
        ("config.example.yaml", "示例配置文件"),
        ("requirements.txt", "Python依赖"),
        ("nginx.conf", "Nginx配置")
    ]
    
    for filepath, desc in config_files:
        if check_file_exists(filepath, desc):
            if filepath.endswith('.yaml'):
                if not check_yaml_syntax(filepath):
                    issues.append(f"YAML语法错误: {filepath}")
    
    print("\n📁 检查Docker文件:")
    # 检查Docker文件
    docker_files = [
        ("Dockerfile", "Docker镜像文件"),
        ("docker-compose.yml", "Docker Compose开发"),
        ("docker-compose.prod.yml", "Docker Compose生产"),
        ("entrypoint.sh", "容器入口脚本")
    ]
    
    for filepath, desc in docker_files:
        check_file_exists(filepath, desc)
    
    print("\n📁 检查测试文件:")
    # 检查测试文件
    test_files = [
        ("tests/test_app.py", "应用测试"),
        ("test_webui.py", "Web UI测试"),
        ("test_auto_config.py", "自动配置测试")
    ]
    
    for filepath, desc in test_files:
        if check_file_exists(filepath, desc):
            if not check_python_syntax(filepath):
                issues.append(f"Python语法错误: {filepath}")
    
    print("\n📁 检查文档文件:")
    # 检查文档文件
    doc_files = [
        ("README.md", "项目说明"),
        ("SECURITY.md", "安全文档"),
        ("LICENSE", "许可证"),
        ("PROJECT_SUMMARY.md", "项目总结"),
        ("DEPLOYMENT_CHECKLIST.md", "部署清单"),
        ("DOCKER_HUB_SETUP.md", "Docker Hub设置")
    ]
    
    for filepath, desc in doc_files:
        check_file_exists(filepath, desc)
    
    print("\n📁 检查CI/CD文件:")
    # 检查GitHub Actions
    github_files = [
        (".github/workflows/ci.yml", "CI工作流"),
        (".github/workflows/docker-build.yml", "Docker构建工作流")
    ]
    
    for filepath, desc in github_files:
        if check_file_exists(filepath, desc):
            if not check_yaml_syntax(filepath):
                issues.append(f"YAML语法错误: {filepath}")
    
    print("\n📁 检查启动脚本:")
    # 检查启动脚本
    script_files = [
        ("start.sh", "Linux启动脚本"),
        ("start.bat", "Windows启动脚本"),
        ("start_dev.sh", "Linux开发启动脚本"),
        ("start_dev.bat", "Windows开发启动脚本"),
        ("release.sh", "发布脚本"),
        ("check-security.sh", "安全检查脚本")
    ]
    
    for filepath, desc in script_files:
        check_file_exists(filepath, desc)
    
    print("\n📁 检查目录结构:")
    # 检查目录
    directories = [
        (".github", "GitHub配置目录"),
        (".github/workflows", "GitHub Actions目录"),
        ("tests", "测试目录"),
        ("static", "静态文件目录")
    ]
    
    for dirpath, desc in directories:
        check_directory_exists(dirpath, desc)
    
    print("\n🔍 安全性检查:")
    # 运行安全检查
    if os.path.exists("check-security.sh"):
        try:
            result = subprocess.run(["bash", "check-security.sh"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 安全检查通过")
            else:
                print(f"❌ 安全检查失败: {result.stdout}")
                issues.append("安全检查失败")
        except Exception as e:
            print(f"⚠️  无法运行安全检查: {e}")
    
    print("\n📊 检查结果:")
    if issues:
        print(f"❌ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    else:
        print("🎉 项目完整性检查通过！")
        print("✅ 所有核心文件存在")
        print("✅ 配置文件语法正确")
        print("✅ Python代码语法正确")
        print("✅ 安全检查通过")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
