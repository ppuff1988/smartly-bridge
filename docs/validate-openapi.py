#!/usr/bin/env python3
"""
OpenAPI 3.1 规范验证脚本
验证 openapi.yaml 文件的结构和完整性
"""

import yaml
import json
import sys
from pathlib import Path

def validate_openapi(file_path):
    """验证 OpenAPI 规范文件"""
    print(f"🔍 正在验证 {file_path}...")
    
    # 1. 验证 YAML 格式
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        print("✅ YAML 格式正确")
    except yaml.YAMLError as e:
        print(f"❌ YAML 格式错误: {e}")
        return False
    
    # 2. 验证必要字段
    required_fields = ['openapi', 'info', 'paths']
    for field in required_fields:
        if field not in spec:
            print(f"❌ 缺少必要字段: {field}")
            return False
    print(f"✅ 包含所有必要字段: {', '.join(required_fields)}")
    
    # 3. 验证 OpenAPI 版本
    version = spec.get('openapi', '')
    if not version.startswith('3.1'):
        print(f"⚠️  警告: OpenAPI 版本为 {version}，建议使用 3.1.x")
    else:
        print(f"✅ OpenAPI 版本: {version}")
    
    # 4. 验证 info 部分
    info = spec.get('info', {})
    required_info = ['title', 'version']
    for field in required_info:
        if field not in info:
            print(f"❌ info 缺少必要字段: {field}")
            return False
    print(f"✅ API 标题: {info['title']}")
    print(f"✅ API 版本: {info['version']}")
    
    # 5. 统计端点
    paths = spec.get('paths', {})
    endpoint_count = sum(len(methods) for methods in paths.values())
    print(f"✅ 共有 {len(paths)} 个路径，{endpoint_count} 个端点")
    
    # 6. 验证 components
    components = spec.get('components', {})
    if 'schemas' in components:
        print(f"✅ 共有 {len(components['schemas'])} 个 Schema 定义")
    
    if 'parameters' in components:
        print(f"✅ 共有 {len(components['parameters'])} 个参数定义")
    
    if 'responses' in components:
        print(f"✅ 共有 {len(components['responses'])} 个响应定义")
    
    # 7. 验证 webhooks（OpenAPI 3.1 特性）
    webhooks = spec.get('webhooks', {})
    if webhooks:
        print(f"✅ 共有 {len(webhooks)} 个 Webhook 定义")
    
    # 8. 检查重复的顶层键
    top_level_keys = list(spec.keys())
    if len(top_level_keys) != len(set(top_level_keys)):
        duplicates = [k for k in set(top_level_keys) if top_level_keys.count(k) > 1]
        print(f"❌ 发现重复的顶层键: {duplicates}")
        return False
    
    # 9. 验证所有 $ref 引用
    print("\n🔗 验证 Schema 引用...")
    refs_valid = validate_refs(spec, components)
    if refs_valid:
        print("✅ 所有 $ref 引用都有效")
    else:
        print("❌ 发现无效的 $ref 引用")
        return False
    
    print("\n" + "="*50)
    print("🎉 OpenAPI 规范验证通过！")
    print("="*50)
    return True

def validate_refs(spec, components):
    """递归验证所有 $ref 引用"""
    def extract_refs(obj, refs=None):
        if refs is None:
            refs = []
        
        if isinstance(obj, dict):
            if '$ref' in obj:
                refs.append(obj['$ref'])
            for value in obj.values():
                extract_refs(value, refs)
        elif isinstance(obj, list):
            for item in obj:
                extract_refs(item, refs)
        
        return refs
    
    # 提取所有引用
    all_refs = extract_refs(spec)
    
    # 验证每个引用
    schemas = components.get('schemas', {})
    parameters = components.get('parameters', {})
    responses = components.get('responses', {})
    
    invalid_refs = []
    for ref in all_refs:
        if ref.startswith('#/components/schemas/'):
            schema_name = ref.split('/')[-1]
            if schema_name not in schemas:
                invalid_refs.append(ref)
        elif ref.startswith('#/components/parameters/'):
            param_name = ref.split('/')[-1]
            if param_name not in parameters:
                invalid_refs.append(ref)
        elif ref.startswith('#/components/responses/'):
            response_name = ref.split('/')[-1]
            if response_name not in responses:
                invalid_refs.append(ref)
    
    if invalid_refs:
        print(f"❌ 发现 {len(invalid_refs)} 个无效引用:")
        for ref in invalid_refs:
            print(f"   - {ref}")
        return False
    
    return True

if __name__ == '__main__':
    file_path = Path(__file__).parent / 'openapi.yaml'
    
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        sys.exit(1)
    
    success = validate_openapi(file_path)
    sys.exit(0 if success else 1)
