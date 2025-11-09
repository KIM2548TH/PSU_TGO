# Toast Notification Utilities for Flask
# ใช้ส่ง toast notifications จาก backend ไปยัง frontend

import json
import urllib.parse
from flask import make_response


def create_toast_response(content='', message='', toast_type='success', status_code=200, **kwargs):
    """
    สร้าง Flask response พร้อม toast notification
    
    Args:
        content (str): เนื้อหา HTML ที่จะส่งกลับ (ถ้ามี)
        message (str): ข้อความ toast
        toast_type (str): ประเภท toast ('success', 'error', 'warning', 'info')
        status_code (int): HTTP status code
        **kwargs: trigger events อื่นๆ เพิ่มเติม
    
    Returns:
        Flask response object พร้อม HX-Trigger header
    
    ตัวอย่างการใช้งาน:
        return create_toast_response('', 'บันทึกสำเร็จ!', 'success')
        return create_toast_response('<div>HTML content</div>', 'เกิดข้อผิดพลาด!', 'error')
    """
    response = make_response(content, status_code)
    
    # สร้าง trigger data
    trigger_data = kwargs.copy()
    
    if message:
        encoded_message = urllib.parse.quote(message)
        trigger_key = f'show{toast_type.capitalize()}'
        trigger_data[trigger_key] = encoded_message
    
    if trigger_data:
        response.headers['HX-Trigger'] = json.dumps(trigger_data)
    
    return response


def success_response(message, content='', **kwargs):
    """สร้าง success response พร้อม success toast"""
    return create_toast_response(content, message, 'success', 200, **kwargs)


def error_response(message, content='', status_code=400, **kwargs):
    """สร้าง error response พร้อม error toast"""
    return create_toast_response(content, message, 'error', status_code, **kwargs)


def warning_response(message, content='', **kwargs):
    """สร้าง warning response พร้อม warning toast"""
    return create_toast_response(content, message, 'warning', 200, **kwargs)


def info_response(message, content='', **kwargs):
    """สร้าง info response พร้อม info toast"""
    return create_toast_response(content, message, 'info', 200, **kwargs)


# Decorator สำหรับจัดการ toast notifications
def with_toast(message=None, toast_type='success'):
    """
    Decorator สำหรับเพิ่ม toast notification ให้กับ view function
    
    ตัวอย่าง:
        @with_toast('บันทึกสำเร็จ!', 'success')
        def save_data():
            # logic here
            return redirect(url_for('home'))
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # ถ้า result เป็น response object แล้ว ให้เพิ่ม header
            if hasattr(result, 'headers') and message:
                encoded_message = urllib.parse.quote(message)
                trigger_key = f'show{toast_type.capitalize()}'
                
                existing_trigger = result.headers.get('HX-Trigger')
                if existing_trigger:
                    try:
                        trigger_data = json.loads(existing_trigger)
                        trigger_data[trigger_key] = encoded_message
                    except json.JSONDecodeError:
                        trigger_data = {trigger_key: encoded_message}
                else:
                    trigger_data = {trigger_key: encoded_message}
                
                result.headers['HX-Trigger'] = json.dumps(trigger_data)
            
            return result
        return wrapper
    return decorator


# Helper functions สำหรับใช้ใน templates (ถ้าต้องการ)
def add_toast_trigger(response, message, toast_type='success'):
    """เพิ่ม toast trigger ให้กับ response ที่มีอยู่แล้ว"""
    if not hasattr(response, 'headers'):
        return response
    
    encoded_message = urllib.parse.quote(message)
    trigger_key = f'show{toast_type.capitalize()}'
    
    existing_trigger = response.headers.get('HX-Trigger')
    if existing_trigger:
        try:
            trigger_data = json.loads(existing_trigger)
            trigger_data[trigger_key] = encoded_message
        except json.JSONDecodeError:
            trigger_data = {trigger_key: encoded_message}
    else:
        trigger_data = {trigger_key: encoded_message}
    
    response.headers['HX-Trigger'] = json.dumps(trigger_data)
    return response


# Constants สำหรับประเภท toast
class ToastType:
    SUCCESS = 'success'
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'