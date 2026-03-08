#!/usr/bin/env python
import re
import os

template_dir = 'templates/malar_app'

# List of templates to fix
templates_to_fix = [
    'home.html',
    'product_list.html',
    'product_detail.html',
    'product_form.html',
    'category_list.html',
    'confirm_delete.html',
    'stock_management.html',
    'analytics_dashboard.html',
    'product_import.html',
    'inventory_report.html',
    'custom_product_form.html'
]

# URL mapping - old_name -> should_be_namespaced
url_mappings = {
    r"'home'": "'malar_app:home'",
    r"'login'": "'malar_app:login'",
    r"'logout'": "'malar_app:logout'",
    r"'product-list'": "'malar_app:product-list'",
    r"'product-detail'": "'malar_app:product-detail'",
    r"'product-create'": "'malar_app:product-create'",
    r"'product-update'": "'malar_app:product-update'",
    r"'product-delete'": "'malar_app:product-delete'",
    r"'product-create-custom'": "'malar_app:product-create-custom'",
    r"'category-list'": "'malar_app:category-list'",
    r"'stock-management'": "'malar_app:stock-management'",
    r"'analytics-dashboard'": "'malar_app:analytics-dashboard'",
    r"'product-import'": "'malar_app:product-import'",
    r"'inventory-report'": "'malar_app:inventory-report'",
}

errors_found = []

for template_name in templates_to_fix:
    filepath = os.path.join(template_dir, template_name)
    
    if not os.path.exists(filepath):
        print(f"⏭️  Skipping {template_name} (not found)")
        continue
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace all URL mappings
        for old_pattern, new_pattern in url_mappings.items():
            # Match {% url 'name' ... %}
            pattern = rf"{{% url {old_pattern}"
            replacement = f"{{% url {new_pattern}"
            content = content.replace(pattern, replacement)
        
        # Check if anything changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Fixed {template_name}")
        else:
            print(f"⏭️  {template_name} - no changes needed")
    
    except Exception as e:
        errors_found.append(f"{template_name}: {str(e)}")
        print(f"❌ Error fixing {template_name}: {str(e)}")

if errors_found:
    print(f"\n⚠️ Errors found:")
    for error in errors_found:
        print(f"  - {error}")
else:
    print("\n✅ All templates checked and fixed!")
