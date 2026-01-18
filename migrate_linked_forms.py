#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Migration Script: แปลง linked_material_name เป็น linked_forms array
รัน: python migrate_linked_forms.py
"""

from pymongo import MongoClient
from urllib.parse import quote_plus
from bson import ObjectId

# MongoDB connection - ลองแบบไม่ใช้ auth ก่อน
host = "127.0.0.1"
port = 27017
db_name = "appdb"

# ลองเชื่อมต่อแบบไม่ใช้ username/password ก่อน
try:
    uri = f"mongodb://{host}:{port}/{db_name}"
    client = MongoClient(uri)
    # ทดสอบการเชื่อมต่อ
    client.admin.command('ping')
    print("✓ เชื่อมต่อแบบไม่ใช้ auth สำเร็จ")
except Exception as e:
    # ถ้าไม่ได้ ลองใช้ auth
    print(f"ไม่สามารถเชื่อมต่อแบบไม่ใช้ auth ได้: {e}")
    print("ลองเชื่อมต่อแบบใช้ auth...")
    username = "admin"
    password = quote_plus("R211@2o25")
    uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource=admin"
    client = MongoClient(uri)

db = client[db_name]
form_collection = db['form_and_formula']


def migrate_linked_forms():
    """แปลงข้อมูลเก่าให้เป็นรูปแบบใหม่"""
    
    print("🔄 เริ่มต้น Migration...")
    print("-" * 60)
    
    # หา forms ทั้งหมดที่เป็น linked
    linked_forms = list(form_collection.find({"is_linked": True}))
    
    total_count = len(linked_forms)
    migrated_count = 0
    skipped_count = 0
    error_count = 0
    
    print(f"พบ {total_count} ฟอร์มที่เป็น linked forms")
    print()
    
    for form in linked_forms:
        try:
            form_id = form['_id']
            form_name = form.get('material_name', 'Unknown')
            print(f"📝 กำลังประมวลผล: {form_name} (ID: {form_id})")
            
            # ตรวจสอบว่ามี linked_forms อยู่แล้วหรือไม่
            if 'linked_forms' in form and form['linked_forms']:
                print(f"   ⏭️  ข้ามไป - มี linked_forms อยู่แล้ว: {form['linked_forms']}")
                skipped_count += 1
                continue
            
            # ตรวจสอบว่ามี linked_material_name หรือไม่
            if 'linked_material_name' not in form or not form['linked_material_name']:
                print(f"   ⚠️  ไม่มี linked_material_name - ตั้งค่าเป็น empty array")
                form_collection.update_one(
                    {'_id': form_id},
                    {'$set': {'linked_forms': []}}
                )
                migrated_count += 1
                continue
            
            linked_mat_name = form['linked_material_name']
            print(f"   🔗 Linked to: {linked_mat_name}")
            
            # ค้นหา form ที่ถูกลิงก์จากชื่อ
            source_form = form_collection.find_one({'material_name': linked_mat_name})
            
            if not source_form:
                print(f"   ❌ ไม่พบฟอร์มต้นฉบับ: {linked_mat_name}")
                # ตั้งค่าเป็น empty array
                form_collection.update_one(
                    {'_id': form_id},
                    {'$set': {'linked_forms': []}}
                )
                error_count += 1
                continue
            
            source_form_id = str(source_form['_id'])
            print(f"   ✅ พบฟอร์มต้นฉบับ ID: {source_form_id}")
            
            # อัพเดท linked_forms และ input_types
            update_data = {
                'linked_forms': [source_form_id]
            }
            
            # อัพเดท input_types ให้มี source_form_id
            if 'input_types' in form and form['input_types']:
                print(f"   🔧 อัพเดท {len(form['input_types'])} input fields...")
                updated_inputs = []
                
                for inp in form['input_types']:
                    # ตรวจสอบว่ามี source_form_id อยู่แล้วหรือไม่
                    if 'source_form_id' not in inp or not inp.get('source_form_id'):
                        inp['source_form_id'] = source_form_id
                    updated_inputs.append(inp)
                
                update_data['input_types'] = updated_inputs
            
            # บันทึก
            form_collection.update_one(
                {'_id': form_id},
                {'$set': update_data}
            )
            print(f"   💾 บันทึกสำเร็จ!")
            migrated_count += 1
            
        except Exception as e:
            print(f"   ❌ เกิดข้อผิดพลาด: {str(e)}")
            error_count += 1
        
        print()
    
    # สรุปผล
    print("=" * 60)
    print("📊 สรุปผลการ Migration:")
    print(f"   ทั้งหมด:        {total_count} ฟอร์ม")
    print(f"   ✅ สำเร็จ:       {migrated_count} ฟอร์ม")
    print(f"   ⏭️  ข้ามไป:      {skipped_count} ฟอร์ม (มีข้อมูลแล้ว)")
    print(f"   ❌ ผิดพลาด:     {error_count} ฟอร์ม")
    print("=" * 60)
    
    if migrated_count > 0:
        print("✨ Migration เสร็จสมบูรณ์!")
    else:
        print("ℹ️  ไม่มีข้อมูลที่ต้อง migrate")


def verify_migration():
    """ตรวจสอบผลการ migration"""
    print("\n🔍 ตรวจสอบผลการ Migration...")
    print("-" * 60)
    
    # นับจำนวน linked forms ที่มี linked_forms
    forms_with_new = form_collection.count_documents({
        'is_linked': True,
        'linked_forms': {'$exists': True, '$ne': []}
    })
    print(f"✅ ฟอร์มที่มี linked_forms (รูปแบบใหม่): {forms_with_new}")
    
    # นับจำนวน linked forms ที่ยังมี linked_material_name อยู่
    forms_with_old = form_collection.count_documents({
        'is_linked': True,
        'linked_material_name': {'$exists': True, '$ne': ""}
    })
    print(f"⚠️  ฟอร์มที่ยังมี linked_material_name (รูปแบบเก่า): {forms_with_old}")
    
    # ตรวจสอบ input_types ที่มี source_form_id
    all_linked = form_collection.find({'is_linked': True})
    inputs_with_source = 0
    for form in all_linked:
        if 'input_types' in form and form['input_types']:
            for inp in form['input_types']:
                if 'source_form_id' in inp and inp['source_form_id']:
                    inputs_with_source += 1
    
    print(f"✅ Input fields ที่มี source_form_id: {inputs_with_source}")
    print("-" * 60)


def remove_deprecated_fields():
    """ลบ field linked_material_name ที่เลิกใช้แล้ว"""
    print("\n🗑️  กำลังลบ field ที่เลิกใช้แล้ว...")
    print("-" * 60)
    
    # ลบ linked_material_name ออกจากทุก document
    result = form_collection.update_many(
        {'linked_material_name': {'$exists': True}},
        {'$unset': {'linked_material_name': ""}}
    )
    
    print(f"✅ ลบ linked_material_name จาก {result.modified_count} ฟอร์ม")
    print("-" * 60)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🔄 Migration Script: linked_material_name → linked_forms")
    print("=" * 60 + "\n")
    
    try:
        print("🔌 เชื่อมต่อฐานข้อมูล...")
        # ทดสอบการเชื่อมต่อ
        client.admin.command('ping')
        print("✅ เชื่อมต่อสำเร็จ!\n")
        
        # รัน migration
        migrate_linked_forms()
        
        # ตรวจสอบผล
        verify_migration()
        
        # ลบ field เก่า
        remove_deprecated_fields()
        
        # ตรวจสอบอีกครั้งหลังลบ
        print("\n🔍 ตรวจสอบอีกครั้งหลังลบ field เก่า...")
        print("-" * 60)
        forms_with_old = form_collection.count_documents({
            'linked_material_name': {'$exists': True}
        })
        print(f"✅ ฟอร์มที่ยังมี linked_material_name: {forms_with_old} (ควรเป็น 0)")
        print("-" * 60)
        
        print("\n✨ เสร็จสิ้น!\n")
        
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดร้ายแรง: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔒 ปิดการเชื่อมต่อฐานข้อมูลแล้ว")

