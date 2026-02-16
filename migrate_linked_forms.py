#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Populate used_by_forms"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import mongoengine
from dotenv import load_dotenv
from urllib.parse import quote_plus
load_dotenv()

# Try without auth first
print("🔌 Connecting without authentication...")
try:
    mongoengine.connect(
        db=os.getenv('MONGODB_DB', 'appdb'),
        host=os.getenv('MONGODB_HOST', '127.0.0.1'),
        port=int(os.getenv('MONGODB_PORT', 27017))
    )
    
    # Import after connection
    from webapp.models.form_and_formula_model import FormAndFormula
    from bson import ObjectId
    
    # Test with actual query
    FormAndFormula.objects(is_linked=True).count()
    print("✅ Connected without authentication\n")
    
except Exception as e:
    print(f"⚠️  Auth required, connecting with credentials...")
    mongoengine.disconnect()
    
    # Connect with auth (like user_clone.py)
    username = os.getenv('MONGODB_USERNAME', 'admin')
    password = os.getenv('MONGODB_PASSWORD', 'R211@2o25')
    host = os.getenv('MONGODB_HOST', '127.0.0.1')
    port = int(os.getenv('MONGODB_PORT', 27017))
    db_name = os.getenv('MONGODB_DB', 'appdb')
    
    mongoengine.connect(
        db=db_name,
        host=host,
        port=port,
        username=username,
        password=password,
        authentication_source='admin'
    )
    
    # Import after connection
    from webapp.models.form_and_formula_model import FormAndFormula
    from bson import ObjectId
    
    print("✅ Connected with authentication\n")

print("\n🔗 Populate used_by_forms\n")

linked_forms = FormAndFormula.objects(is_linked=True)
added = 0
exists = 0

for linked_form in linked_forms:
    
    linked_id = str(linked_form.id)
    print(f"📝 {linked_form.material_name}")
    
    for source_id in linked_form.linked_forms:
        source = FormAndFormula.objects(id=ObjectId(source_id)).first()
        if not source:
            continue
        
        if not hasattr(source, 'used_by_forms'):
            source.used_by_forms = []
        
        if linked_id in source.used_by_forms:
            print(f"   ⏭️  {source.material_name}")
            exists += 1
        else:
            source.used_by_forms.append(linked_id)
            source.save()
            print(f"   ✅ {source.material_name}")
            added += 1

print(f"\n✅ เพิ่ม {added} | มีอยู่แล้ว {exists}\n")
