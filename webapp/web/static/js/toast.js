// Global Toast Notification System
// ใช้งานง่าย: showSuccess('ข้อความ'), showError('ข้อความ'), showWarning('ข้อความ'), showInfo('ข้อความ')

// ฟังก์ชันหลักสำหรับแสดง toast
function showToast(message, type = 'success', duration = 3000) {
  // หา container หรือสร้างใหม่ถ้าไม่มี
  let container = document.getElementById('global-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'global-toast-container';
    container.className = 'fixed top-4 right-4 z-50 space-y-2';
    document.body.appendChild(container);
  }
  
  // สร้าง toast element
  const toast = document.createElement('div');
  const toastId = 'toast-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
  toast.id = toastId;
  
  // กำหนดสีและไอคอนตามประเภท
  let bgColor, iconColor, icon;
  switch (type) {
    case 'success':
      bgColor = 'bg-green-500';
      iconColor = 'text-white';
      icon = 'check-circle';
      break;
    case 'error':
      bgColor = 'bg-red-500';
      iconColor = 'text-white';
      icon = 'alert-circle';
      break;
    case 'warning':
      bgColor = 'bg-yellow-500';
      iconColor = 'text-white';
      icon = 'alert-triangle';
      break;
    case 'info':
    default:
      bgColor = 'bg-blue-500';
      iconColor = 'text-white';
      icon = 'info';
      break;
  }
  
  toast.className = `toast-item transform translate-x-full transition-all duration-300 ease-in-out ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg max-w-sm min-w-[200px] word-wrap break-word`;
  
  toast.innerHTML = `
    <div class="flex items-center gap-2">
      <i data-feather="${icon}" class="w-5 h-5 ${iconColor}"></i>
      <span class="text-sm font-medium flex-1">${message}</span>
      <button onclick="hideToast('${toastId}')" class="ml-2 text-white hover:text-gray-200 transition-colors focus:outline-none">
        <i data-feather="x" class="w-4 h-4"></i>
      </button>
    </div>
  `;
  
  container.appendChild(toast);
  
  // Initialize feather icons
  if (typeof feather !== 'undefined') {
    feather.replace();
  }
  
  // Show toast with animation
  requestAnimationFrame(() => {
    toast.classList.remove('translate-x-full');
  });
  
  // Auto hide after duration
  if (duration > 0) {
    setTimeout(() => {
      hideToast(toastId);
    }, duration);
  }
  
  return toastId;
}

// ฟังก์ชันสำหรับซ่อน toast
function hideToast(toastId) {
  const toast = document.getElementById(toastId);
  if (toast) {
    toast.classList.add('translate-x-full');
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }
}

// ฟังก์ชันสำหรับแสดง toast ประเภทต่างๆ (ใช้งานง่าย)
function showSuccess(message, duration = 3000) {
  return showToast(message, 'success', duration);
}

function showError(message, duration = 5000) {
  return showToast(message, 'error', duration);
}

function showWarning(message, duration = 4000) {
  return showToast(message, 'warning', duration);
}

function showInfo(message, duration = 3000) {
  return showToast(message, 'info', duration);
}

// ฟังก์ชันเพิ่มเติม
function hideAllToasts() {
  const container = document.getElementById('global-toast-container');
  if (container) {
    const toasts = container.querySelectorAll('.toast-item');
    toasts.forEach(toast => {
      toast.classList.add('translate-x-full');
    });
    setTimeout(() => {
      container.innerHTML = '';
    }, 300);
  }
}

// สำหรับ responsive
const toastStyles = `
  @media (max-width: 640px) {
    #global-toast-container {
      left: 1rem;
      right: 1rem;
      top: 1rem;
    }
    
    .toast-item {
      max-width: none;
    }
  }
`;

// เพิ่ม styles ถ้ายังไม่มี
if (!document.getElementById('toast-styles')) {
  const styleSheet = document.createElement('style');
  styleSheet.id = 'toast-styles';
  styleSheet.textContent = toastStyles;
  document.head.appendChild(styleSheet);
}

// ฟังก์ชันสำหรับแสดง toast จาก server response
window.showToastFromResponse = function(response) {
  if (response && response.message) {
    const type = response.type || 'success';
    showToast(response.message, type, response.duration);
  }
};

// Export functions สำหรับการใช้งานใน modules (ถ้าใช้)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    showToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
    hideToast,
    hideAllToasts
  };
}