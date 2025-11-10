  /* ---------- REQUEST TRACKING ---------- */
  // Track all active resume generation requests
  const activeRequests = new Map(); // key: requestId, value: {company, status, element}
  let requestIdCounter = 0;

  function generateRequestId() {
    return `req_${Date.now()}_${++requestIdCounter}`;
  }

  function updateBannerCount() {
    const banner = document.getElementById('processingBanner');
    const bannerCount = document.getElementById('bannerCount');
    const activeCount = Array.from(activeRequests.values()).filter(r => r.status === 'processing').length;
    
    console.log('[DEBUG] Updating banner count. Active:', activeCount, 'Total:', activeRequests.size);
    
    if (activeCount > 0) {
      banner.classList.add('active');
      bannerCount.textContent = activeCount === 1 
        ? 'Processing 1 resume...' 
        : `Processing ${activeCount} resumes...`;
    } else {
      // Keep banner open for 3 seconds to show completed items
      setTimeout(() => {
        const stillActive = Array.from(activeRequests.values()).filter(r => r.status === 'processing').length;
        if (stillActive === 0) {
          banner.classList.remove('active');
        }
      }, 3000);
    }
  }

  function addRequestToUI(requestId, companyName) {
    console.log('[DEBUG] Adding request to UI:', requestId, companyName);
    
    const requestsList = document.getElementById('requestsList');
    if (!requestsList) {
      console.error('[DEBUG] requestsList element not found!');
      return;
    }
    
    const requestItem = document.createElement('div');
    requestItem.className = 'request-item';
    requestItem.id = `request_${requestId}`;
    requestItem.innerHTML = `
      <div class="item-icon">
        <div class="spinner-small"></div>
      </div>
      <div class="item-text">
        <div class="item-company">${companyName || 'Unknown Company'}</div>
        <div class="item-progress" style="font-size: 0.85em; color: var(--text-secondary); margin-top: 2px;">Starting...</div>
      </div>
    `;
    requestsList.appendChild(requestItem);
    
    console.log('[DEBUG] Request item added to DOM, total items:', requestsList.children.length);
    
    activeRequests.set(requestId, {
      company: companyName,
      status: 'processing',
      element: requestItem
    });
    
    console.log('[DEBUG] Active requests count:', activeRequests.size);
    
    updateBannerCount();
  }

  function updateRequestProgress(requestId, progress, message) {
    const request = activeRequests.get(requestId);
    if (request && request.status === 'processing') {
      const progressDiv = request.element.querySelector('.item-progress');
      if (progressDiv) {
        progressDiv.textContent = `${progress}% - ${message || 'Processing...'}`;
        console.log('[BANNER UPDATE] Updated progress for', requestId, ':', progress, '%', message);
      }
    }
  }

  function markRequestComplete(requestId, fileName) {
    const request = activeRequests.get(requestId);
    if (request) {
      request.status = 'completed';
      request.element.classList.add('completed');
      request.element.innerHTML = `
        <div class="item-icon">✓</div>
        <div class="item-text">
          <div class="item-company">${request.company}</div>
          <div class="item-progress" style="color: var(--success);">Completed - ${fileName}</div>
        </div>
      `;
      
      updateBannerCount();
      
      // Remove completed item after 5 seconds
      setTimeout(() => {
        request.element.style.opacity = '0';
        setTimeout(() => {
          request.element.remove();
          activeRequests.delete(requestId);
          updateBannerCount();
        }, 300);
      }, 5000);
    }
  }

  function markRequestFailed(requestId, error) {
    const request = activeRequests.get(requestId);
    if (request) {
      request.status = 'failed';
      request.element.classList.add('failed');
      request.element.innerHTML = `
        <div class="item-icon" style="color: var(--danger);">✗</div>
        <div class="item-text">
          <div class="item-company" style="color: var(--danger);">${request.company}</div>
          <div class="item-progress" style="color: var(--danger);">Failed</div>
        </div>
      `;
      
      updateBannerCount();
      
      // Remove failed item after 8 seconds
      setTimeout(() => {
        request.element.style.opacity = '0';
        setTimeout(() => {
          request.element.remove();
          activeRequests.delete(requestId);
          updateBannerCount();
        }, 300);
      }, 8000);
    }
  }

  function closeProcessingBanner() {
    const banner = document.getElementById('processingBanner');
    banner.classList.remove('active');
  }

  // Alias for backwards compatibility
  function addRequestToBanner(requestId, companyName) {
    return addRequestToUI(requestId, companyName);
  }

  /* ---------- FORM SECTION NAVIGATION ---------- */
  function showFormSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.form-section-panel').forEach(panel => {
      panel.classList.remove('active');
    });
    
    // Remove active from all nav buttons
    document.querySelectorAll('.form-nav-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Show selected section
    const section = document.getElementById(`section-${sectionId}`);
    if (section) {
      section.classList.add('active');
    }
    
    // Mark button as active
    event.target.closest('.form-nav-btn').classList.add('active');
  }

  /* ---------- SCROLL TO TOP ---------- */
  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // Show/hide scroll button based on scroll position
  window.addEventListener('scroll', () => {
    const scrollBtn = document.getElementById('scrollToTop');
    if (window.pageYOffset > 300) {
      scrollBtn.classList.add('visible');
    } else {
      scrollBtn.classList.remove('visible');
    }
  });

  /* ---------- THEME ---------- */
  const themeBtn = document.getElementById('toggleTheme');
  const savedTheme = localStorage.getItem('theme');
  if(savedTheme) document.body.setAttribute('data-theme', savedTheme);
  themeBtn.textContent = savedTheme === 'dark' ? '☀️ Day' : '🌙 Night';
  themeBtn.addEventListener('click', ()=>{
    const dark = document.body.getAttribute('data-theme') === 'dark';
    document.body.setAttribute('data-theme', dark ? 'light' : 'dark');
    localStorage.setItem('theme', dark ? 'light' : 'dark');
    themeBtn.textContent = dark ? '🌙 Night' : '☀️ Day';
  });

  /* ---------- FORM BUILDERS ---------- */
  function addContact(k='',v=''){
    const d=document.createElement('div');
    d.className='entry';
    // Determine placeholder based on key
    let valuePlaceholder = 'Value';
    if (k === 'Phone') valuePlaceholder = '+1 999 999 9999';
    else if (k === 'Email') valuePlaceholder = 'abc@mail.com';
    else if (k === 'LinkedIn') valuePlaceholder = 'https://linkedin.com/in/yourprofile';
    else if (k === 'Portfolio') valuePlaceholder = 'https://yourportfolio.com';
    else if (v) valuePlaceholder = 'URL or value';

    d.innerHTML=`<input placeholder="Label (Phone, Email, LinkedIn, Portfolio)" class="contact-key" value="${k}" ${k ? 'readonly' : ''}>
    <input placeholder="${valuePlaceholder}" class="contact-value" value="${v}">`;
    document.getElementById('contactList').appendChild(d);
  }
  function addSkill(k='',v=''){const d=document.createElement('div');
    d.className='entry';d.innerHTML=`<input placeholder="Category" class="skill-key" value="${k}">
    <input placeholder="Values (comma-separated)" class="skill-value" value="${v}">`;
    document.getElementById('skillsList').appendChild(d);}
  function addExperience(exp=null){const d=document.createElement('div');
  d.className='entry';d.innerHTML=`<input placeholder="Company" class="exp-company" value="${exp?.company||''}">
  <input placeholder="Role" class="exp-role" value="${exp?.role||''}">
  <input placeholder="Period" class="exp-period" value="${exp?.period||''}">
  <div class="bullets"></div><button type="button" class="sub-btn" onclick="addBullet(this)">+ Add Bullet</button>`;
  document.getElementById('experienceList').appendChild(d);
  const bulletsDiv = d.querySelector('.bullets');
  let pts = Array.isArray(exp?.points) ? exp.points : [''];
  // If no points, add one empty bullet
  if (!pts.length) pts = [''];
  // Pass the bulletsDiv directly to addBullet for correct population
  pts.forEach(p => addBullet(bulletsDiv, p));
  }
  function addBullet(btn,text=''){const b=document.createElement('div');b.className='bullet';
    b.innerHTML=`<input placeholder="Achievement..." class="exp-point" value="${text||''}">
    <button class="remove-btn" onclick="this.parentElement.remove()">🗑</button>`;
    // If btn is a .bullets container, append directly; else fallback to previous logic
    if (btn && btn.classList && btn.classList.contains('bullets')) {
      btn.appendChild(b);
    } else if (btn && btn.parentElement && btn.parentElement.querySelector('.bullets')) {
      btn.parentElement.querySelector('.bullets').appendChild(b);
    }
}
  function addEducation(e=null){const d=document.createElement('div');
    d.className='entry';d.innerHTML=`<input placeholder="Degree" class="edu-degree" value="${e?.degree||''}">
    <input placeholder="Institution" class="edu-inst" value="${e?.institution||''}">
    <input placeholder="Year" class="edu-year" value="${e?.year||''}">`;
    document.getElementById('educationList').appendChild(d);}

  function addProject(proj=null){
    const d=document.createElement('div');
    d.className='entry';
    d.innerHTML=`<input placeholder="Project Title" class="proj-title" value="${proj?.title||''}">
    <div class="bullets"></div>
    <button type="button" class="sub-btn" onclick="addProjectBullet(this)">+ Add Bullet</button>`;
    document.getElementById('projectsList').appendChild(d);
    const bulletsDiv = d.querySelector('.bullets');
    let pts = Array.isArray(proj?.bullets) ? proj.bullets : [''];
    if (!pts.length) pts = [''];
    pts.forEach(p => addProjectBullet(bulletsDiv, p));
  }

  function addProjectBullet(btn, text=''){
    const b=document.createElement('div');
    b.className='bullet';
    b.innerHTML=`<input placeholder="Project detail..." class="proj-point" value="${text||''}">
    <button class="remove-btn" onclick="this.parentElement.remove()">🗑</button>`;
    if (btn && btn.classList && btn.classList.contains('bullets')) {
      btn.appendChild(b);
    } else if (btn && btn.parentElement && btn.parentElement.querySelector('.bullets')) {
      btn.parentElement.querySelector('.bullets').appendChild(b);
    }
  }

  function addCertification(cert=null){
    const d=document.createElement('div');
    d.className='entry';
    d.innerHTML=`<input placeholder="Certification Name" class="cert-name" value="${cert?.name||''}">
    <input placeholder="Issuing Organization" class="cert-org" value="${cert?.organization||''}">
    <input placeholder="Year" class="cert-year" value="${cert?.year||''}">`;
    document.getElementById('certificationsList').appendChild(d);
  }

  /* ---------- JSON HANDLERS ---------- */
  function buildJSON(){
    const f=document.getElementById('resumeForm');
    const resume_data = {name:f.name.value,contact:{},summary:f.summary.value,
      technical_skills:{},experience:[],education:[],projects:[],certifications:[]};
    document.querySelectorAll('#contactList .entry').forEach(x=>{
      const k=x.querySelector('.contact-key').value.trim(),v=x.querySelector('.contact-value').value.trim();if(k&&v)resume_data.contact[k.toLowerCase()]=v;});
    document.querySelectorAll('#skillsList .entry').forEach(x=>{
      const k=x.querySelector('.skill-key').value,v=x.querySelector('.skill-value').value;if(k&&v)resume_data.technical_skills[k]=v;});
    document.querySelectorAll('#experienceList .entry').forEach(x=>{
      resume_data.experience.push({company:x.querySelector('.exp-company').value,
        role:x.querySelector('.exp-role').value,period:x.querySelector('.exp-period').value,
        points:Array.from(x.querySelectorAll('.exp-point')).map(i=>i.value.trim()).filter(Boolean)});});
    document.querySelectorAll('#educationList .entry').forEach(x=>{
      resume_data.education.push({degree:x.querySelector('.edu-degree').value,
        institution:x.querySelector('.edu-inst').value,year:x.querySelector('.edu-year').value});});
    document.querySelectorAll('#projectsList .entry').forEach(x=>{
      resume_data.projects.push({title:x.querySelector('.proj-title').value,
        bullets:Array.from(x.querySelectorAll('.proj-point')).map(i=>i.value.trim()).filter(Boolean)});});
    document.querySelectorAll('#certificationsList .entry').forEach(x=>{
      resume_data.certifications.push({name:x.querySelector('.cert-name').value,
        organization:x.querySelector('.cert-org').value,year:x.querySelector('.cert-year').value});});
    const companyNameJD = document.getElementById('companyNameJD') ? document.getElementById('companyNameJD').value : '';
    const jobDescriptionElem = document.getElementById('jobDescriptionTab');
    const job_description_data = {
      job_description: jobDescriptionElem ? jobDescriptionElem.value : '',
      company_name: companyNameJD
    };
    return {resume_data, job_description_data};
  }

  // Helper function to get just the resume data
  function getResumeData() {
    const { resume_data } = buildJSON();
    return resume_data;
  }

  /* ---------- SAVE/LOAD RESUME TEMPLATE ---------- */
  async function saveResumeTemplate() {
    try {
      const resumeData = getResumeData();
      
      // Basic validation
      if (!resumeData.name || resumeData.name.trim() === '') {
        alert('⚠️ Please enter your name before saving the template.');
        return;
      }

      const response = await fetch('/api/user/resume-template', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Basic ' + btoa(currentUsername + ':' + currentPassword)
        },
        body: JSON.stringify({ resume_data: resumeData })
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to save' }));
        throw new Error(error.detail || 'Failed to save resume template');
      }

      const result = await response.json();
      alert('✅ Resume template saved successfully!\n\nIt will auto-load the next time you log in.');
      console.log('Template saved:', result);
      
    } catch (error) {
      console.error('Save template failed:', error);
      alert(`❌ Error saving template: ${error.message}`);
    }
  }

  async function loadResumeTemplate() {
    try {
      console.log('Loading resume template...');
      
      const response = await fetch('/api/user/resume-template', {
        method: 'GET',
        headers: {
          'Authorization': 'Basic ' + btoa(currentUsername + ':' + currentPassword)
        }
      });

      if (!response.ok) {
        console.log('No template found or error loading');
        return;
      }

      const result = await response.json();
      
      if (result.has_template && result.resume_data) {
        console.log('Template loaded, populating form...');
        populateForm(result.resume_data);
        showResult('✅ Resume template loaded!');
        console.log('Template last updated:', result.updated_at);
      } else {
        console.log('No template saved yet');
      }
      
    } catch (error) {
      console.error('Load template failed:', error);
      // Silently fail - don't show error on login if template doesn't exist
    }
  }

  function triggerUpload(){document.getElementById('uploadJSON').click();}
  document.getElementById('uploadJSON').addEventListener('change', e=>{
    const file=e.target.files[0];if(!file)return;
    const r=new FileReader();r.onload=ev=>{try{
      const d=JSON.parse(ev.target.result);
      // Only populate resume data, not job description data
      if(d.resume_data) {
        populateForm(d.resume_data);
      } else {
        populateForm(d);
      }
      // Do NOT populate job description fields from upload
      showResult('✅ Resume JSON Uploaded');
    }catch{alert("Invalid JSON");}};r.readAsText(file);});

  function populateForm(d){
    const f = document.getElementById('resumeForm');
    f.name.value = d.name || '';
    f.summary.value = d.summary || '';
    
    // Handle contact - both old format (string) and new format (object)
    document.getElementById('contactList').innerHTML = '';
    const contact = d.contact || {};
    if (typeof contact === 'string') {
      // Old format: single string - convert to phone field
      addContact('Phone', contact);
    } else if (typeof contact === 'object') {
      // New format: structured object
      Object.entries(contact).forEach(([k, v]) => addContact(k, v));
    }
    if (document.querySelectorAll('#contactList .entry').length === 0) {
      addContact(); // Add empty field if no contact data
    }
    
    document.getElementById('skillsList').innerHTML = '';
    const skills = d.technical_skills || d.skills || {};
    if (Object.keys(skills).length) {
      Object.entries(skills).forEach(([k, v]) => addSkill(k, v));
    } else {
      addSkill();
    }
    document.getElementById('experienceList').innerHTML = '';
    if (d.experience && d.experience.length) {
      d.experience.forEach(e => addExperience(e));
    } else {
      addExperience();
    }
    document.getElementById('educationList').innerHTML = '';
    if (d.education && d.education.length) {
      d.education.forEach(e => addEducation(e));
    } else {
      addEducation();
    }
    document.getElementById('projectsList').innerHTML = '';
    if (d.projects && d.projects.length) {
      d.projects.forEach(p => addProject(p));
    } else {
      addProject();
    }
    document.getElementById('certificationsList').innerHTML = '';
    if (d.certifications && d.certifications.length) {
      d.certifications.forEach(c => addCertification(c));
    } else {
      addCertification();
    }
  }

  function downloadJSON(){
    // Only download resume data (not job description)
    const { resume_data } = buildJSON();
    const blob=new Blob([JSON.stringify(resume_data,null,2)],{type:"application/json"});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download="resume_data.json";a.click();URL.revokeObjectURL(a.href);showResult('💾 Resume JSON Downloaded');}

  async function downloadWordDoc() {
    try {
      console.log('Generating Word document from current resume data...');
      
      const { resume_data } = buildJSON();
      
      // Validate resume data
      if (!resume_data.name || resume_data.name.trim() === '') {
        alert('⚠️ Please enter your name before generating a Word document.');
        return;
      }
      
      // Show loading message
      showResult('⏳ Generating Word document...');
      
      const response = await fetch('/create_resume', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ resume_data })
      });
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Failed to generate document' }));
        throw new Error(error.detail || 'Failed to generate Word document');
      }
      
      // Get the blob from response
      const blob = await response.blob();
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${resume_data.name.replace(/\s+/g, '_')}_Resume.docx`;
      document.body.appendChild(a);
      a.click();
      
      // Cleanup
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      showResult('✅ Word document downloaded!');
      console.log('Word document generated successfully');
      
    } catch (error) {
      console.error('Word generation failed:', error);
      showResult(`❌ Error: ${error.message}`);
    }
  }

  function toggleDownloadMenu() {
    const menu = document.getElementById('downloadOptions');
    menu.classList.toggle('show');
  }

  // Close download menu when clicking outside
  document.addEventListener('click', function(event) {
    const downloadGroup = document.querySelector('.download-group');
    const menu = document.getElementById('downloadOptions');
    
    if (menu && downloadGroup && !downloadGroup.contains(event.target)) {
      menu.classList.remove('show');
    }
  });

  async function generateResume(){
    console.log('[DEBUG] Generate Resume clicked');
    
    // Get selected resume mode
    const resumeModeRadio = document.querySelector('input[name="resumeMode"]:checked');
    const resumeMode = resumeModeRadio ? resumeModeRadio.value : 'complete_jd'; // Default to complete_jd
    
    const {resume_data: resumeObj, job_description_data: jobObj} = buildJSON();
    
    // Generate unique request ID
    const requestId = generateRequestId();
    const companyName = jobObj.company_name || 'Unknown Company';
    
    console.log('[DEBUG] Request ID:', requestId, 'Company:', companyName);
    
    // Add request to UI tracking
    addRequestToUI(requestId, companyName);
    
    const payload = {
      resume_data: resumeObj,
      job_description_data: jobObj,
      mode: resumeMode  // Add mode to payload
    };
    
    // Call new endpoint for JSON output (use correct backend port)
    const apiUrl = 'http://localhost:5001/api/generate_resume_json';
    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      if(res.ok){
        const json = await res.json();
        // Show success message with file name
        const fileName = json.file_name || 'resume.docx';
        const result = json.result || 'Resume generated successfully';
        
        // Mark request as complete in UI
        markRequestComplete(requestId, fileName);
        
        showResult(`✅ ${result} - ${fileName}`);
      }
      else {
        const errorText = await res.text();
        console.error('API Error:', errorText);
        
        // Mark request as failed in UI
        markRequestFailed(requestId, errorText);
        
        showResult('❌ Error generating resume.');
      }
    } catch (error) {
      console.error('Request failed:', error);
      
      // Mark request as failed in UI
      markRequestFailed(requestId, error.message);
      
      showResult('❌ Failed to connect to server.');
    }
  }
  

  function clearAll(){if(!confirm("Clear all fields?"))return;
    document.getElementById('resumeForm').reset();
    document.getElementById('contactList').innerHTML='';
    document.getElementById('skillsList').innerHTML='';
    document.getElementById('experienceList').innerHTML='';
    document.getElementById('educationList').innerHTML='';
    document.getElementById('projectsList').innerHTML='';
    document.getElementById('certificationsList').innerHTML='';
    const jobDescTab = document.getElementById('jobDescriptionTab');
    const companyNameJD = document.getElementById('companyNameJD');
    if (jobDescTab) jobDescTab.value = '';
    if (companyNameJD) companyNameJD.value = '';
    addContact('Phone', '');addContact('Email', '');addContact('LinkedIn', '');
    addSkill();addExperience();addEducation();addProject();addCertification();showResult('🧹 Cleared all fields');}

  function showResult(msg){const r=document.getElementById('result');r.textContent=msg;setTimeout(()=>r.textContent='',4000);}

  /* ---------- ABOUT MODAL ---------- */
  const modal=document.getElementById("aboutModal");
  function openAbout(){modal.style.display="block";}
  function closeAbout(){modal.style.display="none";}
  window.onclick=function(e){if(e.target==modal)modal.style.display="none";}

  /* ---------- FAQ ACCORDION ---------- */
  function toggleFAQ(button) {
    const faqItem = button.parentElement;
    const isActive = faqItem.classList.contains('active');
    
    // Close all FAQ items
    document.querySelectorAll('.faq-item').forEach(item => {
      item.classList.remove('active');
    });
    
    // Open clicked item if it wasn't active
    if (!isActive) {
      faqItem.classList.add('active');
    }
  }

  /* ---------- FAQ SECTION TOGGLE ---------- */
  function toggleFAQSection() {
    const faqSection = document.getElementById('faqSection');
    if (faqSection.classList.contains('active')) {
      faqSection.classList.remove('active');
    } else {
      faqSection.classList.add('active');
      // Scroll to FAQ section smoothly
      setTimeout(() => {
        faqSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }

  // --------- TAB SWITCHING LOGIC ---------
  const tabResumeBtn = document.getElementById('tabResumeBtn');
  const tabEditJDBtn = document.getElementById('tabEditJDBtn');
  const tabDashboardBtn = document.getElementById('tabDashboardBtn');
  const resumeFormContainer = document.getElementById('resumeFormContainer');
  const jobDescTabPanel = document.getElementById('jobDescTabPanel');
  const dashboardTabPanel = document.getElementById('dashboardTabPanel');

  function switchTab(tab) {
    // Remove active from all tabs
    tabResumeBtn.classList.remove('active');
    tabEditJDBtn.classList.remove('active');
    tabDashboardBtn.classList.remove('active');
    resumeFormContainer.classList.remove('active');
    jobDescTabPanel.classList.remove('active');
    dashboardTabPanel.classList.remove('active');

    // Get action bar
    const actionBar = document.getElementById('actionBar');
    
    // Activate the selected tab
    if (tab === 'resume') {
      tabResumeBtn.classList.add('active');
      resumeFormContainer.classList.add('active');
      actionBar.style.display = 'flex'; // Show in View Resume
    } else if (tab === 'jd') {
      tabEditJDBtn.classList.add('active');
      jobDescTabPanel.classList.add('active');
      actionBar.style.display = 'none'; // Hide in Generate Resume
    } else if (tab === 'dashboard') {
      tabDashboardBtn.classList.add('active');
      dashboardTabPanel.classList.add('active');
      actionBar.style.display = 'none'; // Hide in Dashboard
      loadDashboardStats(); // Load stats when dashboard tab is opened
      loadDashboardHistory(); // Load resume history
    }
  }
  
  tabResumeBtn.addEventListener('click', () => switchTab('resume'));
  tabEditJDBtn.addEventListener('click', () => switchTab('jd'));
  tabDashboardBtn.addEventListener('click', () => switchTab('dashboard'));

  // --------- INIT ---------
  // Initialize with common contact fields
  document.getElementById('contactList').innerHTML = '';
  addContact('Phone', '');
  addContact('Email', '');
  addContact('LinkedIn', '');
  addSkill();addExperience();addEducation();addProject();addCertification();
  // Default: show Resume tab
  switchTab('resume');

  // --------- JOB DESC TAB PANEL LOGIC ---------
  const jobDescriptionTab = document.getElementById('jobDescriptionTab');
  
  // Generate Resume Based on JD button
  const generateJDResumeBtn = document.getElementById('generateJDResumeBtn');
  console.log('Generate JD Resume Button found:', generateJDResumeBtn);
  
  if (generateJDResumeBtn) {
    console.log('Adding click listener to Generate JD Resume button');
    generateJDResumeBtn.addEventListener('click', async function() {
      console.log('Generate JD Resume button clicked!');
      
      const jdText = jobDescriptionTab.value.trim();
      const companyName = document.getElementById('companyNameJD').value.trim();
      const jobTitle = document.getElementById('jobTitleJD').value.trim();
      
      console.log('Form values:', { companyName, jobTitle, jdTextLength: jdText.length });
      
      if (!companyName) {
        alert('Please enter the company name!');
        document.getElementById('companyNameJD').focus();
        return;
      }
      
      if (!jobTitle) {
        alert('Please enter the job title!');
        document.getElementById('jobTitleJD').focus();
        return;
      }
      
      if (!jdText) {
        alert('Please paste a job description first!');
        return;
      }

      // Check if user is logged in
      if (!dashboardCredentials) {
        alert('Please login first to generate resumes!');
        switchTab('dashboard');
        return;
      }

      // Get resume data from form
      const resumeData = getResumeData();
      
      // Generate using authenticated endpoint
      try {
        const requestData = {
          company_name: companyName,
          job_title: jobTitle,
          mode: "complete_jd",
          jd: jdText,
          resume_data: resumeData,
          request_id: `req_${Date.now()}_${dashboardCredentials.username}`
        };

        console.log('Sending request:', requestData);

        const response = await fetch(`${API_BASE_URL}/api/generate_resume_json`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + btoa(`${dashboardCredentials.username}:${dashboardCredentials.password}`)
          },
          body: JSON.stringify(requestData)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: 'Request failed' }));
          throw new Error(error.detail || 'Failed to generate resume');
        }

        const result = await response.json();
        console.log('Success:', result);
        
        // Add to processing banner
        addRequestToUI(result.request_id, companyName);
        
        // Show success message and switch to dashboard
        alert(`Resume generation started! Request ID: ${result.request_id}\n\nGo to Dashboard to track progress.`);
        switchTab('dashboard');
        loadDashboardHistory();
        
      } catch (error) {
        console.error('Generation failed:', error);
        alert(`Error: ${error.message}`);
      }
    });
  } else {
    console.error('Generate JD Resume button NOT found in DOM!');
  }

  // Load Sample JD for the tab textarea
  function loadSampleJobDescTab() {
    const sampleText = `We are looking for a skilled Software Engineer with experience in JavaScript, React, and Node.js. The candidate should have strong problem-solving skills and the ability to work in a fast-paced environment. Responsibilities include developing new features, optimizing performance, and collaborating with cross-functional teams.`;
    if (jobDescriptionTab) jobDescriptionTab.value = sampleText;
  }
  // Optionally, allow loading sample JD when double-clicking the textarea
  if (jobDescriptionTab) {
    jobDescriptionTab.addEventListener('dblclick', loadSampleJobDescTab);
  }

  /* ---------- INITIALIZE PAGE ---------- */
  // Show Basic Info section by default
  window.addEventListener('DOMContentLoaded', function() {
    const basicSection = document.getElementById('section-basic');
    const basicBtn = document.querySelector('.form-nav-btn');
    
    if (basicSection) {
      basicSection.classList.add('active');
    }
    if (basicBtn) {
      basicBtn.classList.add('active');
    }
  });

  /* ---------- DASHBOARD FUNCTIONALITY ---------- */
  const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5001'
    : '';

  let dashboardCredentials = null;
  let dashboardPollIntervals = {};
  let currentUsername = null;
  let currentPassword = null;

  // Auth Tab Switching
  function switchAuthTab(tab) {
    const loginTabBtn = document.getElementById('loginTabBtn');
    const registerTabBtn = document.getElementById('registerTabBtn');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    if (tab === 'login') {
      loginTabBtn.classList.add('active');
      registerTabBtn.classList.remove('active');
      loginForm.classList.add('active');
      registerForm.classList.remove('active');
    } else {
      registerTabBtn.classList.add('active');
      loginTabBtn.classList.remove('active');
      registerForm.classList.add('active');
      loginForm.classList.remove('active');
    }
  }

  // Dashboard Panels Switching
  function switchDashTab(tab) {
    const genBtn = document.getElementById('dashGenTab');
    const histBtn = document.getElementById('dashHistTab');
    const genPanel = document.getElementById('dashGeneratePanel');
    const histPanel = document.getElementById('dashHistoryPanel');

    if (tab === 'generate') {
      genBtn.classList.add('active');
      histBtn.classList.remove('active');
      genPanel.classList.add('active');
      histPanel.style.display = 'none';
    } else {
      histBtn.classList.add('active');
      genBtn.classList.remove('active');
      histPanel.style.display = 'block';
      genPanel.classList.remove('active');
      loadDashboardHistory();
    }
  }

  // Show Message
  function showDashMessage(message, type = 'info') {
    const authMsg = document.getElementById('authMessage');
    const dashMsg = document.getElementById('dashboardMessage');
    
    const msgBox = dashboardCredentials ? dashMsg : authMsg;
    msgBox.style.display = 'block';
    msgBox.style.background = type === 'error' ? '#fed7d7' : type === 'success' ? '#c6f6d5' : '#bee3f8';
    msgBox.style.color = type === 'error' ? '#742a2a' : type === 'success' ? '#22543d' : '#2c5282';
    msgBox.style.border = `1px solid ${type === 'error' ? '#fc8181' : type === 'success' ? '#9ae6b4' : '#90cdf4'}`;
    msgBox.textContent = message;
    setTimeout(() => msgBox.style.display = 'none', 5000);
  }

  // API Call Helper
  async function dashApiCall(endpoint, options = {}) {
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers
    };

    if (dashboardCredentials) {
      headers['Authorization'] = 'Basic ' + btoa(`${dashboardCredentials.username}:${dashboardCredentials.password}`);
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      
      // Extract the error message from backend
      const errorMessage = error.detail || error.message || 'Request failed';
      
      throw new Error(errorMessage);
    }

    return response.json();
  }

  // Handle Register
  async function handleDashboardRegister() {
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const confirm = document.getElementById('registerPasswordConfirm').value;

    if (!username || !password) {
      showDashMessage('Please fill in all fields', 'error');
      return;
    }

    if (password !== confirm) {
      showDashMessage('Passwords do not match!', 'error');
      return;
    }

    try {
      await dashApiCall('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ user_id: username, password })
      });

      showDashMessage('Account created! Please login.', 'success');
      switchAuthTab('login');
      document.getElementById('loginUsername').value = username;
    } catch (error) {
      showDashMessage(error.message, 'error');
    }
  }

  // Handle Login
  async function handleDashboardLogin() {
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) {
      showDashMessage('Please enter username and password', 'error');
      return;
    }

    dashboardCredentials = { username, password };

    try {
      await dashApiCall('/api/auth/login', { method: 'POST' });
      
      // Show dashboard view
      document.getElementById('authView').style.display = 'none';
      document.getElementById('dashboardView').style.display = 'block';
      
      loadDashboardStats();
      loadDashboardHistory();
    } catch (error) {
      dashboardCredentials = null;
      // Display specific error message from backend
      const errorMessage = error.message || 'Login failed. Please try again.';
      showDashMessage(errorMessage, 'error');
    }
  }

  // Handle Logout
  function handleDashboardLogout() {
    dashboardCredentials = null;
    document.getElementById('authView').style.display = 'block';
    document.getElementById('dashboardView').style.display = 'none';
    
    // Clear poll intervals
    Object.values(dashboardPollIntervals).forEach(clearInterval);
    dashboardPollIntervals = {};
    
    // Clear forms
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
  }

  // Load User Stats
  async function loadDashboardStats() {
    try {
      const stats = await dashApiCall('/api/user/stats');
      
      // Hide "Processing Now" card if zero, otherwise highlight it
      const processingClass = stats.active_jobs === 0 ? 'stat-card zero-data' : 'stat-card';
      const processingDisplay = stats.active_jobs === 0 ? 'style="display: none;"' : '';
      
      document.getElementById('statsCards').innerHTML = `
        <div class="stat-card">
          <div class="stat-icon">📊</div>
          <div class="stat-value">${stats.total_resumes}</div>
          <div class="stat-label">Total Resumes</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">✨</div>
          <div class="stat-value">${stats.today_resumes}</div>
          <div class="stat-label">Generated Today</div>
        </div>
        <div class="${processingClass}" ${processingDisplay}>
          <div class="stat-icon">⚡</div>
          <div class="stat-value">${stats.active_jobs}</div>
          <div class="stat-label">Processing Now</div>
        </div>
      `;
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  }

  // Load Resume File
  function loadDashResumeFile(event) {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        document.getElementById('dashResumeJSON').value = e.target.result;
      };
      reader.readAsText(file);
    }
  }

  // Handle Generate Resume
  async function handleDashboardGenerate() {
    const companyName = document.getElementById('dashCompanyName').value;
    const jobTitle = document.getElementById('dashJobTitle').value;
    const jd = document.getElementById('dashJobDescription').value;
    const mode = document.getElementById('dashMode').value;
    const resumeJSONText = document.getElementById('dashResumeJSON').value;

    if (!companyName || !jobTitle || !jd) {
      showDashMessage('Please fill in company name, job title, and job description', 'error');
      return;
    }

    let resumeData;
    try {
      resumeData = resumeJSONText ? JSON.parse(resumeJSONText) : {};
    } catch (e) {
      showDashMessage('Invalid JSON format in resume data!', 'error');
      return;
    }

    const requestData = {
      company_name: companyName,
      job_title: jobTitle,
      mode: mode,
      jd: jd,
      resume_data: resumeData,
      job_description_data: {
        company_name: companyName,
        job_title: jobTitle
      }
    };

    const btn = document.getElementById('dashGenerateBtn');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
      const result = await dashApiCall('/api/generate_resume_json', {
        method: 'POST',
        body: JSON.stringify(requestData)
      });

      showDashMessage(`Resume generation started! Request ID: ${result.request_id}`, 'success');
      
      // Switch to history tab
      switchDashTab('history');
      
      // Start polling for this job
      startDashboardPolling(result.request_id);
      
    } catch (error) {
      showDashMessage(error.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Generate Resume';
    }
  }

  // Start Polling Job Status
  function startDashboardPolling(requestId) {
    // Stop existing polling if it exists
    if (dashboardPollIntervals[requestId]) {
      console.log('[POLLING] Polling already exists for:', requestId, '- skipping');
      return;
    }

    console.log('[POLLING] Starting polling for:', requestId);
    
    dashboardPollIntervals[requestId] = setInterval(async () => {
      try {
        const status = await dashApiCall(`/api/jobs/${requestId}/status`);
        console.log('[POLLING] Update received for', requestId);
        console.log('[POLLING] Status:', status.status);
        console.log('[POLLING] Progress:', status.progress);
        console.log('[POLLING] Message:', status.message);
        console.log('[POLLING] Full data:', JSON.stringify(status, null, 2));
        
        // Update processing banner with progress
        if (status.status === 'processing' && status.progress !== undefined) {
          updateRequestProgress(requestId, status.progress, status.message);
        }
        
        updateDashboardJobCard(requestId, status);

        if (status.status === 'completed') {
          console.log('[POLLING] Job completed, stopping polling for:', requestId);
          clearInterval(dashboardPollIntervals[requestId]);
          delete dashboardPollIntervals[requestId];
          markRequestComplete(requestId, `${status.company_name}_${status.job_title}_Resume.docx`);
          loadDashboardStats();
          // Reload history to update UI without restarting polling
          setTimeout(() => loadDashboardHistory(), 100);
        } else if (status.status === 'failed') {
          console.log('[POLLING] Job failed, stopping polling for:', requestId);
          clearInterval(dashboardPollIntervals[requestId]);
          delete dashboardPollIntervals[requestId];
          markRequestFailed(requestId, status.error_message);
          loadDashboardStats();
          // Reload history to update UI without restarting polling
          setTimeout(() => loadDashboardHistory(), 100);
        }
      } catch (error) {
        console.error('[POLLING] Polling error:', error);
      }
    }, 2000);
  }

  // Update Job Card/Row
  function updateDashboardJobCard(requestId, data) {
    console.log('[DASHBOARD UPDATE] Request ID:', requestId);
    console.log('[DASHBOARD UPDATE] Data received:', JSON.stringify(data, null, 2));
    
    const row = document.querySelector(`tr[data-request-id="${requestId}"]`);
    console.log('[DASHBOARD UPDATE] Found row:', row ? 'YES' : 'NO');
    
    if (!row) {
      console.log('[DASHBOARD UPDATE] Row not found, reloading history');
      loadDashboardHistory();
      return;
    }

    // Update status badge (3rd column)
    const statusCell = row.cells[2];
    if (statusCell) {
      const badge = statusCell.querySelector('.status-badge');
      if (badge) {
        badge.className = `status-badge status-${data.status}`;
        badge.textContent = data.status;
        console.log('[DASHBOARD UPDATE] Updated status badge to:', data.status);
      }
    }

    // Update progress (4th column)
    const progressCell = row.cells[3];
    console.log('[DASHBOARD UPDATE] Progress cell exists:', !!progressCell);
    console.log('[DASHBOARD UPDATE] Current status:', data.status);
    console.log('[DASHBOARD UPDATE] Progress value:', data.progress);
    
    if (progressCell) {
      if (data.status === 'processing' || data.status === 'pending') {
        const progressFill = progressCell.querySelector('.progress-fill');
        const progressText = progressCell.querySelector('.progress-text');
        
        console.log('[DASHBOARD UPDATE] Progress fill element:', !!progressFill);
        console.log('[DASHBOARD UPDATE] Progress text element:', !!progressText);
        
        if (progressFill) {
          const newWidth = `${data.progress}%`;
          progressFill.style.width = newWidth;
          console.log('[DASHBOARD UPDATE] Set progress bar width to:', newWidth);
          console.log('[DASHBOARD UPDATE] Actual width after set:', progressFill.style.width);
        }
        if (progressText) {
          const newText = `${data.progress}%`;
          progressText.textContent = newText;
          console.log('[DASHBOARD UPDATE] Set progress text to:', newText);
          console.log('[DASHBOARD UPDATE] Actual text after set:', progressText.textContent);
        }
      } else if (data.status === 'completed') {
        progressCell.innerHTML = '<span style="color: var(--success); font-weight: 600;">✓ 100%</span>';
        console.log('[DASHBOARD UPDATE] Set completed status');
      } else if (data.status === 'failed') {
        progressCell.innerHTML = '<span style="color: var(--danger);">✗ Failed</span>';
        console.log('[DASHBOARD UPDATE] Set failed status');
      }
    }

    // Update actions (6th column) - using kebab menu
    const actionsCell = row.cells[5];
    if (actionsCell) {
      const companyName = row.cells[0].textContent;
      const jobTitle = row.cells[1].textContent;
      
      if (data.status === 'completed') {
        // Replace entire cell with kebab menu
        actionsCell.className = 'actions-cell';
        actionsCell.innerHTML = `
          <button class="kebab-menu-btn" onclick="toggleKebabMenu(event, '${requestId}')">⋮</button>
          <div class="kebab-dropdown" id="kebab-${requestId}">
            <button class="success" onclick="downloadResumeDocx('${requestId}', '${companyName}', '${jobTitle}')">
              <span class="menu-icon">📄</span>
              <span>Download Resume</span>
            </button>
            <button class="primary" onclick="downloadJobDescription('${requestId}', '${companyName}', '${jobTitle}')">
              <span class="menu-icon">📋</span>
              <span>View Job Description</span>
            </button>
            <button class="danger" onclick="deleteResume('${requestId}')">
              <span class="menu-icon">🗑️</span>
              <span>Delete</span>
            </button>
          </div>
        `;
      } else if (data.status === 'failed') {
        // Show failed state in kebab menu
        actionsCell.className = 'actions-cell';
        actionsCell.innerHTML = `
          <button class="kebab-menu-btn" onclick="toggleKebabMenu(event, '${requestId}')">⋮</button>
          <div class="kebab-dropdown" id="kebab-${requestId}">
            <button disabled style="opacity: 0.5; cursor: not-allowed;">
              <span class="menu-icon">❌</span>
              <span>Generation Failed</span>
            </button>
            <button class="danger" onclick="deleteResume('${requestId}')">
              <span class="menu-icon">🗑️</span>
              <span>Delete</span>
            </button>
          </div>
        `;
      }
    }
  }

  // Pagination state
  let currentPage = 1;
  let pageSize = 20;
  let totalResumes = 0;

  // Helper: Get relative time
  function getRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  // Change page size
  function changePageSize() {
    pageSize = parseInt(document.getElementById('pageSizeSelect').value);
    currentPage = 1;
    loadDashboardHistory();
  }

  // Change page
  function goToPage(page) {
    currentPage = page;
    loadDashboardHistory();
  }

  // Render pagination
  function renderPagination(total, current, size) {
    const totalPages = Math.ceil(total / size);
    const paginationContainer = document.getElementById('paginationContainer');
    
    if (totalPages <= 1) {
      paginationContainer.style.display = 'none';
      return;
    }

    paginationContainer.style.display = 'flex';

    const start = (current - 1) * size + 1;
    const end = Math.min(current * size, total);

    let paginationHTML = `
      <div class="pagination-info">
        Showing ${start}-${end} of ${total} resumes
      </div>
      <div class="pagination-controls">
        <button class="pagination-btn" onclick="goToPage(1)" ${current === 1 ? 'disabled' : ''}>
          «
        </button>
        <button class="pagination-btn" onclick="goToPage(${current - 1})" ${current === 1 ? 'disabled' : ''}>
          ‹
        </button>
    `;

    // Show page numbers
    const maxButtons = 5;
    let startPage = Math.max(1, current - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    
    if (endPage - startPage < maxButtons - 1) {
      startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      paginationHTML += `
        <button class="pagination-btn ${i === current ? 'active' : ''}" onclick="goToPage(${i})">
          ${i}
        </button>
      `;
    }

    paginationHTML += `
        <button class="pagination-btn" onclick="goToPage(${current + 1})" ${current === totalPages ? 'disabled' : ''}>
          ›
        </button>
        <button class="pagination-btn" onclick="goToPage(${totalPages})" ${current === totalPages ? 'disabled' : ''}>
          »
        </button>
      </div>
    `;

    paginationContainer.innerHTML = paginationHTML;
  }
  
  // Load Job History - Modern Clean Table with Pagination
  async function loadDashboardHistory() {
    try {
      const offset = (currentPage - 1) * pageSize;
      const data = await dashApiCall(`/api/user/jobs?limit=${pageSize}&offset=${offset}`);
      const tbody = document.getElementById('resumeHistoryBody');
      
      totalResumes = data.count;

      if (data.count === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 60px 20px; color: var(--text-secondary);"><p style="font-size: 1.1em; margin: 0; font-weight: 500;">📄 No resumes yet</p><p style="margin: 8px 0 0 0; font-size: 0.9em;">Start creating your first resume!</p></td></tr>';
        return;
      }

      tbody.innerHTML = data.jobs.map(job => {
        const statusClass = job.status.toLowerCase();
        const statusText = job.status.charAt(0).toUpperCase() + job.status.slice(1);
        const relativeTime = getRelativeTime(job.created_at);
        
        // Determine status display
        let statusContent = '';
        if (job.status === 'processing' || job.status === 'pending') {
          statusContent = `
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="status-badge status-${statusClass}">${statusText}</span>
              <div class="progress-bar">
                <div class="progress-fill" style="width: ${job.progress}%"></div>
              </div>
              <span style="font-size: 12px; color: var(--text-secondary);">${job.progress}%</span>
            </div>
          `;
        } else {
          statusContent = `<span class="status-badge status-${statusClass}">${statusText}</span>`;
        }
        
        return `
          <tr data-request-id="${job.request_id}">
            <td>${job.company_name || 'N/A'}</td>
            <td>${job.job_title || 'N/A'}</td>
            <td>${statusContent}</td>
            <td style="color: var(--text-secondary);">${relativeTime}</td>
            <td class="actions-cell">
              <button class="kebab-menu-btn" onclick="toggleKebabMenu(event, '${job.request_id}')">⋮</button>
              <div class="kebab-dropdown" id="kebab-${job.request_id}">
                ${job.status === 'completed' ? `
                  <button class="success" onclick="downloadResumeDocx('${job.request_id}', '${job.company_name}', '${job.job_title}')">
                    <span class="menu-icon">📄</span>
                    <span>Download Resume</span>
                  </button>
                  <button class="primary" onclick="downloadJobDescription('${job.request_id}', '${job.company_name}', '${job.job_title}')">
                    <span class="menu-icon">📋</span>
                    <span>View Job Description</span>
                  </button>
                ` : job.status === 'processing' || job.status === 'pending' ? `
                  <button class="primary" onclick="checkDashboardStatus('${job.request_id}')">
                    <span class="menu-icon">🔄</span>
                    <span>Refresh Status</span>
                  </button>
                ` : `
                  <button disabled style="opacity: 0.5; cursor: not-allowed;">
                    <span class="menu-icon">❌</span>
                    <span>Generation Failed</span>
                  </button>
                `}
                <button class="danger" onclick="deleteResume('${job.request_id}')">
                  <span class="menu-icon">🗑️</span>
                  <span>Delete</span>
                </button>
              </div>
            </td>
          </tr>
        `;
      }).join('');

      // Render pagination
      renderPagination(totalResumes, currentPage, pageSize);

      // Start polling for active jobs
      data.jobs.forEach(job => {
        if (job.status === 'processing' || job.status === 'pending') {
          startDashboardPolling(job.request_id);
        }
      });

    } catch (error) {
      console.error('Failed to load history:', error);
    }
  }

  // Toggle Kebab Menu
  function toggleKebabMenu(event, requestId) {
    event.stopPropagation();
    const dropdown = document.getElementById(`kebab-${requestId}`);
    const allDropdowns = document.querySelectorAll('.kebab-dropdown');
    
    // Close all other dropdowns
    allDropdowns.forEach(d => {
      if (d !== dropdown) d.classList.remove('show');
    });
    
    // Toggle current dropdown
    dropdown.classList.toggle('show');
  }
  
  // Close kebab menus when clicking outside
  document.addEventListener('click', () => {
    document.querySelectorAll('.kebab-dropdown').forEach(d => d.classList.remove('show'));
  });
  
  // Delete Resume
  async function deleteResume(requestId) {
    if (!confirm('Are you sure you want to delete this resume? This action cannot be undone.')) {
      return;
    }
    
    try {
      await dashApiCall(`/api/jobs/${requestId}`, { method: 'DELETE' });
      showDashMessage('Resume deleted successfully', 'success');
      await loadDashboardHistory(); // Reload the list
    } catch (error) {
      console.error('Delete failed:', error);
      showDashMessage('Failed to delete resume', 'error');
    }
  }

  // Download Resume as DOCX (on-the-fly generation)
  async function downloadResumeDocx(requestId, companyName, jobTitle) {
    try {
      // Fetch the resume JSON
      const data = await dashApiCall(`/api/jobs/${requestId}/result`);
      
      if (!data.final_resume) {
        showDashMessage('Resume data not found', 'error');
        return;
      }

      // Call the backend to generate DOCX on-the-fly
      const response = await fetch(`${API_BASE_URL}/api/jobs/${requestId}/download`, {
        headers: {
          'Authorization': 'Basic ' + btoa(`${dashboardCredentials.username}:${dashboardCredentials.password}`)
        }
      });

      if (!response.ok) {
        throw new Error('Failed to generate resume');
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${companyName}_${jobTitle}_Resume.docx`.replace(/[^a-z0-9_\-\.]/gi, '_');
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      showDashMessage('Resume downloaded successfully!', 'success');
    } catch (error) {
      console.error('Download failed:', error);
      showDashMessage('Failed to download resume', 'error');
    }
  }

  // Download Job Description
  async function downloadJobDescription(requestId, companyName, jobTitle) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/jobs/${requestId}/download-jd`, {
        headers: {
          'Authorization': 'Basic ' + btoa(`${dashboardCredentials.username}:${dashboardCredentials.password}`)
        }
      });

      if (!response.ok) {
        throw new Error('Failed to download job description');
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${companyName}_${jobTitle}_JD.txt`.replace(/[^a-z0-9_\-\.]/gi, '_');
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      showDashMessage('Job description downloaded successfully!', 'success');
    } catch (error) {
      console.error('JD download failed:', error);
      showDashMessage('Failed to download job description', 'error');
    }
  }

  // Check Status
  async function checkDashboardStatus(requestId) {
    console.log('Checking status for:', requestId);
    try {
      const status = await dashApiCall(`/api/jobs/${requestId}/status`);
      console.log('Status received:', status);
      updateDashboardJobCard(requestId, status);
      showDashMessage(`Progress: ${status.progress}%`, 'success');
    } catch (error) {
      console.error('Status check failed:', error);
      showDashMessage(error.message, 'error');
    }
  }

  // View Resume JSON
  async function viewDashboardResume(requestId) {
    try {
      const data = await dashApiCall(`/api/jobs/${requestId}/result`);
      const json = JSON.stringify(data.final_resume, null, 2);
      
      const newWindow = window.open('', '_blank');
      newWindow.document.write(`
        <html>
        <head><title>Resume JSON - ${data.company_name}</title></head>
        <body style="font-family: monospace; padding: 20px; background: #1a202c; color: #e2e8f0;">
          <h2 style="color: #90cdf4;">${data.company_name} - ${data.job_title}</h2>
          <pre style="background: #2d3748; padding: 20px; border-radius: 8px; overflow: auto;">${json}</pre>
        </body>
        </html>
      `);
    } catch (error) {
      showDashMessage(error.message, 'error');
    }
  }

  // Download Resume
  function downloadDashboardResume(requestId) {
    const url = `${API_BASE_URL}/api/jobs/${requestId}/download`;
    
    if (dashboardCredentials) {
      fetch(url, {
        headers: {
          'Authorization': 'Basic ' + btoa(`${dashboardCredentials.username}:${dashboardCredentials.password}`)
        }
      })
      .then(response => response.blob())
      .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `resume_${requestId}.docx`;
        a.click();
        window.URL.revokeObjectURL(url);
      })
      .catch(error => {
        showDashMessage('Download failed: ' + error.message, 'error');
      });
    }
  }

  // Cleanup on page unload
  window.addEventListener('beforeunload', () => {
    Object.values(dashboardPollIntervals).forEach(clearInterval);
  });

  /* ---------- MAIN AUTH FUNCTIONALITY ---------- */
  
  // Switch Main Auth Tabs
  function switchMainAuthTab(tab) {
    const loginBtn = document.getElementById('mainLoginTabBtn');
    const registerBtn = document.getElementById('mainRegisterTabBtn');
    const loginForm = document.getElementById('mainLoginForm');
    const registerForm = document.getElementById('mainRegisterForm');

    if (tab === 'login') {
      loginBtn.classList.add('active');
      registerBtn.classList.remove('active');
      loginForm.classList.add('active');
      registerForm.classList.remove('active');
    } else {
      registerBtn.classList.add('active');
      loginBtn.classList.remove('active');
      registerForm.classList.add('active');
      loginForm.classList.remove('active');
    }
  }

  // Show Main Auth Message
  function showMainAuthMessage(message, type = 'info') {
    const msgBox = document.getElementById('mainAuthMessage');
    msgBox.style.display = 'block';
    msgBox.style.background = type === 'error' ? '#fed7d7' : type === 'success' ? '#c6f6d5' : '#bee3f8';
    msgBox.style.color = type === 'error' ? '#742a2a' : type === 'success' ? '#22543d' : '#2c5282';
    msgBox.style.border = `1px solid ${type === 'error' ? '#fc8181' : type === 'success' ? '#9ae6b4' : '#90cdf4'}`;
    msgBox.textContent = message;
    setTimeout(() => msgBox.style.display = 'none', 5000);
  }

  // Handle Main Register
  async function handleMainRegister() {
    const username = document.getElementById('mainRegisterUsername').value;
    const password = document.getElementById('mainRegisterPassword').value;
    const confirm = document.getElementById('mainRegisterPasswordConfirm').value;

    if (!username || !password) {
      showMainAuthMessage('Please fill in all fields', 'error');
      return;
    }

    if (password !== confirm) {
      showMainAuthMessage('Passwords do not match!', 'error');
      return;
    }

    try {
      await dashApiCall('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ user_id: username, password })
      });

      showMainAuthMessage('Account created! Please login.', 'success');
      switchMainAuthTab('login');
      document.getElementById('mainLoginUsername').value = username;
    } catch (error) {
      showMainAuthMessage(error.message, 'error');
    }
  }

  // Handle Main Login
  async function handleMainLogin() {
    const username = document.getElementById('mainLoginUsername').value;
    const password = document.getElementById('mainLoginPassword').value;

    if (!username || !password) {
      showMainAuthMessage('Please enter username and password', 'error');
      return;
    }

    console.log('Attempting login for user:', username);
    dashboardCredentials = { username, password };
    
    // Store credentials globally for template load
    currentUsername = username;
    currentPassword = password;

    try {
      const result = await dashApiCall('/api/auth/login', { method: 'POST' });
      console.log('Login successful:', result);
      
      // Hide auth screen, show main app
      document.getElementById('authScreen').style.display = 'none';
      document.getElementById('mainApp').style.display = 'block';
      
      // Show logout button and username in header
      document.getElementById('headerUserInfo').textContent = `👤 ${username}`;
      document.getElementById('headerUserInfo').style.display = 'inline';
      document.getElementById('logoutBtn').style.display = 'inline-block';
      
      // Show header and footer
      document.getElementById('mainHeader').style.display = 'flex';
      document.getElementById('mainFooter').style.display = 'block';
      
      // Load stats (for dashboard tab)
      loadDashboardStats();
      loadDashboardHistory();
      
      // Auto-load saved resume template
      await loadResumeTemplate();
      
    } catch (error) {
      console.error('Login failed:', error);
      dashboardCredentials = null;
      currentUsername = null;
      currentPassword = null;
      showMainAuthMessage(error.message || 'Login failed', 'error');
    }
  }

  // Handle Main Logout
  function handleMainLogout() {
    if (!confirm('Are you sure you want to logout?')) return;
    
    dashboardCredentials = null;
    currentUsername = null;
    currentPassword = null;
    
    // Show auth screen, hide main app
    document.getElementById('authScreen').style.display = 'grid';
    document.getElementById('mainApp').style.display = 'none';
    
    // Hide logout button and username in header
    document.getElementById('headerUserInfo').style.display = 'none';
    document.getElementById('logoutBtn').style.display = 'none';
    
    // Hide header and footer
    document.getElementById('mainHeader').style.display = 'none';
    document.getElementById('mainFooter').style.display = 'none';
    
    // Clear forms
    document.getElementById('mainLoginUsername').value = '';
    document.getElementById('mainLoginPassword').value = '';
    document.getElementById('mainRegisterUsername').value = '';
    document.getElementById('mainRegisterPassword').value = '';
    document.getElementById('mainRegisterPasswordConfirm').value = '';
    
    // Clear poll intervals
    Object.values(dashboardPollIntervals).forEach(clearInterval);
    dashboardPollIntervals = {};
    
    // Switch back to login tab
    switchMainAuthTab('login');
  }

  // On page load, check if user is already logged in (from sessionStorage)
  window.addEventListener('DOMContentLoaded', () => {
    // Auth screen is shown by default (no auto-login)
  });

