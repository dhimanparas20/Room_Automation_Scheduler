// No need to populate minuteSelect since we now use a single text input for time
const token = localStorage.getItem('token');
if (!token) {
  window.location.href = '/login';
}

// Helper function to format a Date object to "dd/mm/yyyy, hh:mm:ss AM/PM"
function formatCurrentTime(date) {
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  let hour = date.getHours();
  const minute = String(date.getMinutes()).padStart(2, '0');
  const second = String(date.getSeconds()).padStart(2, '0');
  const ampm = hour >= 12 ? 'PM' : 'AM';
  hour = hour % 12;
  if (hour === 0) hour = 12;
  return `${day}/${month}/${year}, ${String(hour).padStart(2, '0')}:${minute}:${second} ${ampm}`;
}

// Update current time every second in 12-hour format
function updateCurrentTime() {
  const now = new Date();
  document.getElementById('currentTime').innerText = 'Current Time: ' + formatCurrentTime(now);
}
updateCurrentTime();
setInterval(updateCurrentTime, 1000);

// Helper function to format ISO datetime string to "dd/mm/yyyy, hh:mm AM/PM"
function formatDateTime(isoString) {
  const date = new Date(isoString);
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const year = date.getFullYear();
  let hour = date.getHours();
  const minute = String(date.getMinutes()).padStart(2, '0');
  const ampm = hour >= 12 ? 'PM' : 'AM';
  hour = hour % 12;
  if (hour === 0) hour = 12;
  return `${day}/${month}/${year}, ${String(hour).padStart(2, '0')}:${minute} ${ampm}`;
}

// Helper function: Convert a 24-hour time string "HH:MM" to 12-hour format object
function convertTo12Hour(time24) {
  const parts = time24.split(':');
  let hour = parseInt(parts[0]);
  const minute = parts[1];
  let ampm = "AM";
  if (hour === 0) {
    hour = 12;
  } else if (hour >= 12) {
    if (hour > 12) hour = hour - 12;
    ampm = "PM";
  }
  return { hour: hour, minute: minute, ampm: ampm };
}

// Toggle the label of the AM/PM switch based on its state
const ampmToggle = document.getElementById('ampmToggle');
ampmToggle.addEventListener('change', function() {
  this.nextElementSibling.innerText = this.checked ? 'PM' : 'AM';
});

// Update Action toggle label based on state
const actionToggle = document.getElementById('actionToggle');
const actionLabel = document.getElementById('actionLabel');
actionToggle.addEventListener('change', function() {
  actionLabel.innerText = this.checked ? 'Turn On' : 'Turn Off';
});
actionLabel.innerText = actionToggle.checked ? 'Turn On' : 'Turn Off';

// Update Schedule Type toggle label based on state
const scheduleTypeToggle = document.getElementById('scheduleTypeToggle');
const scheduleTypeLabel = document.getElementById('scheduleTypeLabel');
scheduleTypeToggle.addEventListener('change', function() {
  scheduleTypeLabel.innerText = this.checked ? 'One-Time' : 'Daily Schedule';
});
scheduleTypeLabel.innerText = scheduleTypeToggle.checked ? 'One-Time' : 'Daily Schedule';

// References to date container
const dateInputContainer = document.getElementById('dateInputContainer');
scheduleTypeToggle.addEventListener('change', function() {
  dateInputContainer.style.display = this.checked ? 'block' : 'none';
});

// New function to get time from the text input (in 12-hour format) and convert it to 24-hour format "HH:MM"
function getTimeValue() {
  const timeInput = document.getElementById('timeInput').value;
  const pattern = /^(0?[1-9]|1[0-2]):([0-5][0-9])$/;
  const match = timeInput.match(pattern);
  if (!match) return "";
  let hour = parseInt(match[1]);
  const minute = match[2];
  const isPM = ampmToggle.checked;
  if (isPM) {
    if (hour !== 12) hour += 12;
  } else {
    if (hour === 12) hour = 0;
  }
  return String(hour).padStart(2, '0') + ':' + minute;
}

async function fetchSchedules(){
  const response = await fetch('/api/schedules', {
    headers: { 'token': token }
  });
  const schedules = await response.json();
  const tbody = document.getElementById('scheduleTable').getElementsByTagName('tbody')[0];
  tbody.innerHTML = '';
  schedules.reverse().forEach((schedule) => {
    const row = tbody.insertRow();
    const friendlyName = deviceMapping.find(d => d.value === schedule.device)?.name || schedule.device;
    row.insertCell(0).innerText = friendlyName;
    row.insertCell(1).innerText = schedule.action === 1 ? 'On' : 'Off';
    row.insertCell(2).innerText = schedule.schedule_type;
    
    let displayTime = schedule.time;
    if (schedule.schedule_type === 'daily') {
      const t = convertTo12Hour(schedule.time);
      displayTime = t.hour + ':' + t.minute + ' ' + t.ampm;
      row.dataset.rawTime = schedule.time;
    } else {
      const parts = schedule.time.split('T');
      if(parts.length === 2){
        displayTime = parts[0] + ', ' + (() => {
          const t = convertTo12Hour(parts[1]);
          return t.hour + ':' + t.minute + ' ' + t.ampm;
        })();
      }
    }
    row.insertCell(3).innerText = displayTime;
    
    const statusCell = row.insertCell(4);
    if (schedule.schedule_type === 'daily') {
      statusCell.innerText = schedule.last_triggered ? formatDateTime(schedule.last_triggered) : "-";
    } else {
      statusCell.innerHTML = schedule.executed ? `<span style="color:green;">Executed</span>` : `<span style="color:red;">Pending</span>`;
    }
    
    const activeCell = row.insertCell(5);
    const switchDiv = document.createElement("div");
    switchDiv.className = "form-check form-switch";
    const activeToggle = document.createElement("input");
    activeToggle.className = "form-check-input";
    activeToggle.type = "checkbox";
    activeToggle.checked = schedule.active !== false;
    activeToggle.dataset.id = schedule._id;
    if (schedule.schedule_type === 'one-time' && schedule.executed) {
      activeToggle.disabled = true;
    }
    switchDiv.appendChild(activeToggle);
    activeCell.appendChild(switchDiv);
    activeToggle.addEventListener('change', async function() {
      const newState = this.checked;
      const response = await fetch(`/api/schedules/${this.dataset.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'token': token
        },
        body: JSON.stringify({ active: newState })
      });
      const data = await response.json();
      if (!response.ok) {
        alert(data.message || "Error updating schedule active state");
      }
      fetchSchedules();
    });

    const actionsCell = row.insertCell(6);
    if (schedule.schedule_type === 'one-time' && schedule.executed) {
      actionsCell.innerHTML = `<button class="btn btn-sm btn-danger deleteBtn" data-id="${schedule._id}">Delete</button>`;
    } else {
      actionsCell.innerHTML = `
        <button class="btn btn-sm btn-info editBtn" data-id="${schedule._id}">Edit</button>
        <button class="btn btn-sm btn-danger deleteBtn" data-id="${schedule._id}">Delete</button>
      `;
    }
  });
}

document.getElementById('scheduleForm').addEventListener('submit', async function(e) {
  e.preventDefault();
  const scheduleId = document.getElementById('scheduleId').value;
  const device = document.getElementById('device').value;
  const action = document.getElementById('actionToggle').checked ? 1 : 0;
  const scheduleType = document.getElementById('scheduleTypeToggle').checked ? 'one-time' : 'daily';
  let time24 = getTimeValue();
  if (!time24) {
    alert('Please enter a valid time in hh:mm format.');
    return;
  }
  let timeString = time24;
  if (scheduleType === 'one-time') {
    const date = document.getElementById('date').value;
    if (!date) {
      alert('Please select a date for one-time schedule');
      return;
    }
    timeString = date + 'T' + time24;
  }
  const scheduleData = {
    token: token,
    device: device,
    action: action,
    schedule_type: scheduleType,
    time: timeString
  };
  let response;
  if (scheduleId) {
    response = await fetch(`/api/schedules/${scheduleId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'token': token
      },
      body: JSON.stringify(scheduleData)
    });
  } else {
    response = await fetch('/api/schedules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'token': token },
      body: JSON.stringify(scheduleData)
    });
  }
  const data = await response.json();
  if (response.ok) {
    document.getElementById('scheduleForm').reset();
    document.getElementById('scheduleId').value = '';
    fetchSchedules();
  } else {
    alert(data.message || "Error saving schedule");
  }
});

document.getElementById('scheduleTable').addEventListener('click', async function(e) {
  if (e.target.classList.contains('editBtn')) {
    const scheduleId = e.target.getAttribute('data-id');
    const row = e.target.parentElement.parentElement;
    document.getElementById('scheduleId').value = scheduleId;
    const deviceValue = deviceMapping.find(d => d.name === row.cells[0].innerText)?.value || row.cells[0].innerText;
    document.getElementById('device').value = deviceValue;
    document.getElementById('actionToggle').checked = row.cells[1].innerText === 'On';
    document.getElementById('scheduleTypeToggle').checked = row.cells[2].innerText === 'one-time';
    actionLabel.innerText = document.getElementById('actionToggle').checked ? 'Turn On' : 'Turn Off';
    scheduleTypeLabel.innerText = document.getElementById('scheduleTypeToggle').checked ? 'One-Time' : 'Daily Schedule';
    if (row.cells[2].innerText === 'one-time') {
      let parts = row.cells[3].innerText.split(', ');
      if (parts.length === 2) {
        document.getElementById('date').value = parts[0];
        const timeParts = parts[1].split(' ');
        const timeValue = timeParts[0];
        document.getElementById('timeInput').value = timeValue;
        const ampm = timeParts[1];
        document.getElementById('ampmToggle').checked = (ampm === 'PM');
        document.getElementById('ampmToggle').nextElementSibling.innerText = ampm;
        dateInputContainer.style.display = 'block';
      }
    } else {
      const rawTime = row.dataset.rawTime;
      const t = convertTo12Hour(rawTime);
      document.getElementById('timeInput').value = `${t.hour}:${t.minute}`;
      document.getElementById('ampmToggle').checked = (t.ampm === 'PM');
      document.getElementById('ampmToggle').nextElementSibling.innerText = t.ampm;
      dateInputContainer.style.display = 'none';
    }
  } else if (e.target.classList.contains('deleteBtn')) {
    const scheduleId = e.target.getAttribute('data-id');
    if (confirm('Are you sure you want to delete this schedule?')) {
      const response = await fetch(`/api/schedules/${scheduleId}`, {
        method: 'DELETE',
        headers: { 'token': token }
      });
      const data = await response.json();
      if (response.ok) {
        fetchSchedules();
      } else {
        alert(data.message || "Error deleting schedule");
      }
    }
  }
});

document.getElementById('logoutBtn').addEventListener('click', function(){
  localStorage.removeItem('token');
  window.location.href = '/login';
});

// Initial load of schedules
fetchSchedules();
