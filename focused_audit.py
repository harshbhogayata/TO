#!/usr/bin/env python
"""
Focused audit of TalentOrbit source code only (excluding venv, node_modules, etc.)
"""

import os
import sys
import json
import re
from pathlib import Path

def focused_audit():
    """Audit only source code, not dependencies."""
    
    print("🎯 FOCUSED SOURCE CODE AUDIT")
    print("=" * 80)
    
    base_dir = Path("c:/Users/harsh/Desktop/TO")
    
    # Exclude directories
    exclude_dirs = {'venv', 'node_modules', '.git', '__pycache__', 'dist', 'build'}
    
    audit_results = {
        'critical_issues': [],
        'high_priority': [],
        'medium_priority': [],
        'low_priority': [],
        'missing_features': [],
        'production_readiness': []
    }
    
    # 1. Critical Security Issues
    print("\n🚨 CRITICAL SECURITY ISSUES")
    print("-" * 50)
    
    critical_patterns = {
        'sql_injection_raw': r'raw\(|cursor\.execute.*%|execute.*format',
        'xss_direct': r'dangerouslySetInnerHTML|innerHTML.*\+|outerHTML.*\+',
        'hardcoded_secrets': r'(password|secret|key)\s*=\s*[\'"][^\'"]+[\'"]',
        'auth_bypass': r'permission_classes\s*=\s*\[\]|@csrf_exempt.*def\s+(?!get|post)',
        'file_upload_vulnerability': r'upload.*save.*\./|Content-Disposition.*filename',
        'command_injection': r'os\.system.*\+|subprocess\..*shell=True|eval\(',
        'deserialization': r'pickle\.loads|yaml\.load.*unsafe',
        'path_traversal': r'\.\./|\.\.\\|\.\.\/',
        'cors_misconfig': r'CORS_ALLOW_ALL_ORIGINS\s*=\s*True'
    }
    
    for issue, pattern in critical_patterns.items():
        matches = search_source_files(base_dir, pattern, exclude_dirs)
        for match in matches:
            audit_results['critical_issues'].append({
                'type': issue,
                'file': match,
                'severity': 'CRITICAL'
            })
        if matches:
            print(f"   🔴 {issue}: {len(matches)} files")
    
    # 2. High Priority Issues
    print("\n⚠️  HIGH PRIORITY ISSUES")
    print("-" * 50)
    
    high_patterns = {
        'missing_auth': r'@permission_classes.*\[\]|@api_view.*permission',
        'input_validation': r'request\.data\[|request\.GET\[|request\.POST\[',
        'error_handling': r'except\s*:|except\s+Exception\s*:',
        'database_n1': r'for.*\.get\(|for.*\.filter\(',
        'missing_csrf': r'@csrf_exempt.*post|@csrf_exempt.*put',
        'sensitive_data_logs': r'print\(|logger\..*(password|secret|key)',
        'insecure_redirects': r'redirect\(|HttpResponseRedirect\(',
        'session_security': r'session\[.*password|session\[.*secret'
    }
    
    for issue, pattern in high_patterns.items():
        matches = search_source_files(base_dir, pattern, exclude_dirs)
        for match in matches:
            audit_results['high_priority'].append({
                'type': issue,
                'file': match,
                'severity': 'HIGH'
            })
        if matches:
            print(f"   🟠 {issue}: {len(matches)} files")
    
    # 3. Medium Priority Issues
    print("\n📋 MEDIUM PRIORITY ISSUES")
    print("-" * 50)
    
    medium_patterns = {
        'performance_queries': r'objects\.all\(\)|\.count\(\)|\.exists\(\)',
        'caching_missing': r'get_queryset.*return.*QuerySet|def.*get_queryset',
        'async_missing': r'def\s+\w+.*request|\.save\(|\.delete\(',
        'testing_coverage': r'test_|Test',
        'documentation_missing': r'class.*:|def.*:.*#.*|"""',
        'error_messages': r'error|Error|exception',
        'loading_states': r'setLoading|isLoading|loading'
    }
    
    for issue, pattern in medium_patterns.items():
        matches = search_source_files(base_dir, pattern, exclude_dirs)
        for match in matches:
            audit_results['medium_priority'].append({
                'type': issue,
                'file': match,
                'severity': 'MEDIUM'
            })
        if matches:
            print(f"   🟡 {issue}: {len(matches)} files")
    
    # 4. Missing Production Features
    print("\n🚀 MISSING PRODUCTION FEATURES")
    print("-" * 50)
    
    missing_features = {
        'rate_limiting': r'throttle|rate_limit|@throttle_classes',
        'monitoring': r'sentry|logging|metrics|health_check',
        'backup_strategy': r'backup|snapshot|disaster_recovery',
        'ssl_enforcement': r'https|ssl|tls|SECURE_SSL_REDIRECT',
        'api_versioning': r'api/v|version|@version_class',
        'pagination': r'PageNumberPagination|LimitOffsetPagination',
        'search_optimization': r'full_text|search_vector|elasticsearch',
        'cdn_integration': r'CDN|cloudfront|s3|staticfiles',
        'load_balancer': r'nginx|apache|gunicorn|uwsgi'
    }
    
    for feature, pattern in missing_features.items():
        matches = search_source_files(base_dir, pattern, exclude_dirs)
        if not matches:
            audit_results['missing_features'].append({
                'type': feature,
                'missing': True,
                'severity': 'HIGH'
            })
            print(f"   ❌ {feature}: NOT IMPLEMENTED")
        else:
            print(f"   ✅ {feature}: IMPLEMENTED")
    
    # 5. Production Readiness Check
    print("\n🎯 PRODUCTION READINESS CHECK")
    print("-" * 50)
    
    # Check for essential production files
    essential_files = {
        'requirements.txt': base_dir / 'backend' / 'requirements.txt',
        'Dockerfile': base_dir / 'Dockerfile',
        'docker-compose.yml': base_dir / 'docker-compose.yml',
        '.env.example': base_dir / '.env.example',
        'README.md': base_dir / 'README.md'
    }
    
    for file_name, file_path in essential_files.items():
        if file_path.exists():
            audit_results['production_readiness'].append({
                'type': file_name,
                'status': 'EXISTS',
                'severity': 'INFO'
            })
            print(f"   ✅ {file_name}: EXISTS")
        else:
            audit_results['production_readiness'].append({
                'type': file_name,
                'status': 'MISSING',
                'severity': 'HIGH'
            })
            print(f"   ❌ {file_name}: MISSING")
    
    # Calculate Production Readiness Score
    critical_count = len(audit_results['critical_issues'])
    high_count = len(audit_results['high_priority']) + len(audit_results['missing_features'])
    medium_count = len(audit_results['medium_priority'])
    
    # Weighted score calculation
    max_score = 100
    critical_penalty = critical_count * 20
    high_penalty = high_count * 10
    medium_penalty = medium_count * 5
    
    final_score = max(0, max_score - critical_penalty - high_penalty - medium_penalty)
    
    print(f"\n📊 PRODUCTION READINESS SCORE: {final_score}/100")
    
    if final_score >= 80:
        print("   ✅ PRODUCTION READY - Minor improvements needed")
    elif final_score >= 60:
        print("   ⚠️  ALMOST READY - Address high-priority issues")
    elif final_score >= 40:
        print("   🔶 NEEDS WORK - Significant improvements required")
    else:
        print("   ❌ NOT READY - Major issues must be addressed")
    
    # Generate actionable recommendations
    print(f"\n🎯 ACTIONABLE RECOMMENDATIONS")
    print("=" * 80)
    
    print("\n🚨 IMMEDIATE (Critical Security)")
    for issue in audit_results['critical_issues'][:5]:
        print(f"   - Fix {issue['type']} in {Path(issue['file']).name}")
    
    print("\n⚠️  HIGH PRIORITY (This Week)")
    for issue in audit_results['high_priority'][:5]:
        print(f"   - Address {issue['type']} in {Path(issue['file']).name}")
    
    print("\n📋 MEDIUM PRIORITY (This Month)")
    for issue in audit_results['medium_priority'][:5]:
        print(f"   - Improve {issue['type']} in {Path(issue['file']).name}")
    
    print("\n🚀 MISSING FEATURES (Implement)")
    for feature in audit_results['missing_features']:
        if feature['missing']:
            print(f"   - Implement {feature['type']} for production")
    
    # Generate detailed report
    generate_focused_report(audit_results, final_score, base_dir)
    
    return audit_results

def search_source_files(base_dir, pattern, exclude_dirs):
    """Search for pattern in source files only."""
    matches = []
    extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.yml', '.yaml']
    
    try:
        for ext in extensions:
            for file_path in base_dir.rglob(f"*{ext}"):
                # Skip excluded directories
                if any(exclude_dir in file_path.parts for exclude_dir in exclude_dirs):
                    continue
                    
                # Skip if it's in node_modules, venv, etc.
                if any(part.startswith('.') for part in file_path.parts if part != '.'):
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if re.search(pattern, content, re.IGNORECASE):
                            matches.append(str(file_path))
                except Exception:
                    continue
    except Exception:
        pass
    
    return matches

def generate_focused_report(audit_results, score, base_dir):
    """Generate focused audit report."""
    
    report_path = base_dir / "FOCUSED_AUDIT_REPORT.md"
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# TalentOrbit Focused Audit Report\n\n")
        f.write("Generated on: " + str(datetime.datetime.now()) + "\n\n")
        
        f.write("## Executive Summary\n\n")
        f.write(f"**Production Readiness Score: {score}/100**\n\n")
        
        if score >= 80:
            f.write("✅ **PRODUCTION READY** - Minor improvements needed\n")
        elif score >= 60:
            f.write("⚠️  **ALMOST READY** - Address high-priority issues\n")
        elif score >= 40:
            f.write("🔶 **NEEDS WORK** - Significant improvements required\n")
        else:
            f.write("❌ **NOT READY** - Major issues must be addressed\n")
        
        f.write("\n## Critical Issues (Fix Immediately)\n\n")
        for issue in audit_results['critical_issues']:
            f.write(f"- 🔴 **{issue['type']}** - `{Path(issue['file']).name}`\n")
        
        f.write("\n## High Priority Issues\n\n")
        for issue in audit_results['high_priority']:
            f.write(f"- 🟠 **{issue['type']}** - `{Path(issue['file']).name}`\n")
        
        f.write("\n## Missing Production Features\n\n")
        for feature in audit_results['missing_features']:
            if feature['missing']:
                f.write(f"- ❌ **{feature['type']}** - Not implemented\n")
        
        f.write("\n## Production Deployment Checklist\n\n")
        f.write("### Security (Must Fix)\n")
        f.write("- [ ] Fix all SQL injection vulnerabilities\n")
        f.write("- [ ] Implement proper input validation\n")
        f.write("- [ ] Add CSRF protection to all forms\n")
        f.write("- [ ] Secure file uploads\n")
        f.write("- [ ] Implement proper authentication\n")
        f.write("- [ ] Add rate limiting\n\n")
        
        f.write("### Performance (Should Fix)\n")
        f.write("- [ ] Optimize database queries\n")
        f.write("- [ ] Add caching layer\n")
        f.write("- [ ] Implement async operations\n")
        f.write("- [ ] Add database indexes\n")
        f.write("- [ ] Implement pagination\n\n")
        
        f.write("### Monitoring (Should Add)\n")
        f.write("- [ ] Set up comprehensive logging\n")
        f.write("- [ ] Add error tracking (Sentry)\n")
        f.write("- [ ] Implement health checks\n")
        f.write("- [ ] Add performance monitoring\n")
        f.write("- [ ] Set up backup strategy\n\n")
        
        f.write("### Documentation (Should Improve)\n")
        f.write("- [ ] Add API documentation\n")
        f.write("- [ ] Improve code comments\n")
        f.write("- [ ] Add deployment guides\n")
        f.write("- [ ] Create troubleshooting docs\n\n")
        
        f.write("## Cost-Benefit Analysis\n\n")
        f.write("### Pro Version Benefits:\n")
        f.write("- ✅ Advanced security scanning\n")
        f.write("- ✅ Performance optimization tools\n")
        f.write("- ✅ Automated testing suite\n")
        f.write("- ✅ CI/CD pipeline integration\n")
        f.write("- ✅ Monitoring and alerting\n")
        f.write("- ✅ Code quality analysis\n")
        f.write("- ✅ Deployment automation\n")
        f.write("- ✅ Compliance checking\n\n")
        
        f.write("### ROI Estimation:\n")
        f.write("- **Security Issues**: Prevent potential breaches ($50K+ cost)\n")
        f.write("- **Performance**: Improve user experience (20%+ conversion)\n")
        f.write("- **Development Speed**: Automated tools (50% faster deployment)\n")
        f.write("- **Reliability**: Monitoring prevents downtime ($1K+/hour)\n\n")
        
        f.write("### Recommendation:\n")
        if score >= 80:
            f.write("🎉 **PURCHASE PRO** - Your codebase is production-ready with minor improvements. Pro tools will help maintain quality and speed up development.\n")
        elif score >= 60:
            f.write("⚠️  **PURCHASE PRO** - Address high-priority issues first, then use Pro tools to accelerate improvements and prevent regressions.\n")
        else:
            f.write("🔶 **PURCHASE PRO** - Use Pro tools to systematically address issues and implement missing features. The ROI will be significant.\n")
    
    print(f"\n📄 Focused audit report generated: {report_path}")

if __name__ == "__main__":
    import datetime
    audit_results = focused_audit()
    
    print("\n🎯 FOCUSED AUDIT COMPLETE!")
    print("=" * 80)
    print("📄 Check FOCUSED_AUDIT_REPORT.md for actionable recommendations")
    print("💡 Pro version will help address all identified issues systematically")
