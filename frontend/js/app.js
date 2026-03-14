(function () {
  const loginView = document.getElementById('login-view');
  const domainsView = document.getElementById('domains-view');
  const dashboardsView = document.getElementById('dashboards-view');
  const dashboardDetailView = document.getElementById('dashboard-detail-view');
  const loginForm = document.getElementById('login-form');
  const loginError = document.getElementById('login-error');
  const domainsList = document.getElementById('domains-list');
  const userInfo = document.getElementById('user-info');
  const addDomainForm = document.getElementById('add-domain-form');
  const domainForm = document.getElementById('domain-form');
  const domainError = document.getElementById('domain-error');
  const logoutLink = document.getElementById('logout-link');
  const dashboardsList = document.getElementById('dashboards-list');
  const dashboardForm = document.getElementById('dashboard-form');
  const dashboardDomainsFieldset = document.getElementById('dashboard-domains-fieldset');
  const dashboardFormError = document.getElementById('dashboard-form-error');
  const dashboardDetailTitle = document.getElementById('dashboard-detail-title');
  const dashboardWidget = document.getElementById('dashboard-widget');
  const ingestJobsView = document.getElementById('ingest-jobs-view');
  const ingestJobDetailView = document.getElementById('ingest-job-detail-view');
  const ingestJobsList = document.getElementById('ingest-jobs-list');
  const ingestJobDetailTitle = document.getElementById('ingest-job-detail-title');
  const ingestJobDetailContent = document.getElementById('ingest-job-detail-content');
  const auditView = document.getElementById('audit-view');
  const auditEventsWrap = document.getElementById('audit-events-wrap');
  const auditLinkWrap = document.getElementById('audit-link-wrap');
  const apikeysView = document.getElementById('apikeys-view');
  const apikeysListWrap = document.getElementById('apikeys-list-wrap');
  const apikeysLinkWrap = document.getElementById('apikeys-link-wrap');
  const usersView = document.getElementById('users-view');
  const usersListWrap = document.getElementById('users-list-wrap');
  const usersLinkWrap = document.getElementById('users-link-wrap');
  const searchView = document.getElementById('search-view');
  const searchForm = document.getElementById('search-form');
  const searchDomainsFieldset = document.getElementById('search-domains-fieldset');
  const searchResultsWrap = document.getElementById('search-results-wrap');
  const searchPagination = document.getElementById('search-pagination');
  const searchFormError = document.getElementById('search-form-error');
  const uploadView = document.getElementById('upload-view');
  const uploadForm = document.getElementById('upload-form');
  const uploadTextarea = document.getElementById('upload-textarea');
  const uploadFileInput = document.getElementById('upload-file');
  const uploadFormError = document.getElementById('upload-form-error');
  const uploadFormSuccess = document.getElementById('upload-form-success');
  const reportDetailModal = document.getElementById('report-detail-modal');
  const reportDetailTitle = document.getElementById('report-detail-title');
  const reportDetailSummary = document.getElementById('report-detail-summary');
  const reportDetailRecords = document.getElementById('report-detail-records');
  const reportDetailClose = document.getElementById('report-detail-close');

  var currentDashboardId = null;
  var currentDashboardName = null;
  var currentDashboardData = null;
  var currentUserRole = null;
  var currentDashboardPage = 1;
  var currentDashboardPageSize = 50;

  function hideAllViews() {
    loginView.classList.add('hidden');
    domainsView.classList.add('hidden');
    if (dashboardsView) dashboardsView.classList.add('hidden');
    if (dashboardDetailView) dashboardDetailView.classList.add('hidden');
    if (ingestJobsView) ingestJobsView.classList.add('hidden');
    if (ingestJobDetailView) ingestJobDetailView.classList.add('hidden');
    if (auditView) auditView.classList.add('hidden');
    if (apikeysView) apikeysView.classList.add('hidden');
    if (usersView) usersView.classList.add('hidden');
    if (searchView) searchView.classList.add('hidden');
    if (uploadView) uploadView.classList.add('hidden');
  }

  function showLogin() {
    hideAllViews();
    loginView.classList.remove('hidden');
  }

  function showDomains() {
    hideAllViews();
    domainsView.classList.remove('hidden');
  }

  function showDashboards() {
    hideAllViews();
    if (dashboardsView) dashboardsView.classList.remove('hidden');
  }

  function showDashboardDetail() {
    hideAllViews();
    if (dashboardDetailView) dashboardDetailView.classList.remove('hidden');
  }

  function showIngestJobs() {
    hideAllViews();
    if (ingestJobsView) ingestJobsView.classList.remove('hidden');
  }

  function showIngestJobDetail() {
    hideAllViews();
    if (ingestJobDetailView) ingestJobDetailView.classList.remove('hidden');
  }

  function showAudit() {
    hideAllViews();
    if (auditView) auditView.classList.remove('hidden');
  }

  function showApikeys() {
    hideAllViews();
    if (apikeysView) apikeysView.classList.remove('hidden');
  }

  function showUsers() {
    hideAllViews();
    if (usersView) usersView.classList.remove('hidden');
  }

  function showSearch() {
    hideAllViews();
    if (searchView) searchView.classList.remove('hidden');
  }

  function showUpload() {
    hideAllViews();
    if (uploadView) uploadView.classList.remove('hidden');
  }

  function setUploadError(msg) {
    if (uploadFormError) {
      uploadFormError.textContent = msg || '';
      uploadFormError.classList.toggle('hidden', !msg);
    }
    if (uploadFormSuccess) uploadFormSuccess.classList.add('hidden');
  }

  function setUploadSuccess(html) {
    if (uploadFormSuccess) {
      uploadFormSuccess.innerHTML = html || '';
      uploadFormSuccess.classList.toggle('hidden', !html);
    }
    if (uploadFormError) uploadFormError.classList.add('hidden');
  }

  function loadUploadPage() {
    setUploadError('');
    setUploadSuccess('');
    if (uploadTextarea) uploadTextarea.value = '';
    if (uploadFileInput) uploadFileInput.value = '';
  }

  function arrayBufferToBase64(buffer) {
    var binary = '';
    var bytes = new Uint8Array(buffer);
    for (var i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
  }

  function isGzipFile(filename, bytes) {
    if (filename && (filename.endsWith('.gz') || filename.endsWith('.gzip'))) return true;
    if (bytes && bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b) return true;
    return false;
  }

  function getCsrfToken() {
    var match = document.cookie.match(/dmarc_csrf=([^;]+)/);
    return match ? match[1] : '';
  }

  function doUpload(content, contentEncoding) {
    var body = {
      source: 'web',
      reports: [{
        content_type: 'application/xml',
        content_encoding: contentEncoding,
        content_transfer_encoding: 'base64',
        content: content
      }]
    };
    fetch('/api/v1/reports/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify(body)
    })
      .then(function (r) {
        if (r.ok) return r.json();
        return r.json().catch(function () { return {}; }).then(function (d) {
          throw new Error(d.detail || 'Upload failed: ' + r.status);
        });
      })
      .then(function (data) {
        var jobId = data.job_id || 'unknown';
        setUploadSuccess('Report submitted. Job ID: <a href="#" class="upload-job-link" data-job-id="' + escapeHtml(jobId) + '">' + escapeHtml(jobId) + '</a>');
        if (uploadTextarea) uploadTextarea.value = '';
        if (uploadFileInput) uploadFileInput.value = '';
        var link = document.querySelector('.upload-job-link');
        if (link) {
          link.addEventListener('click', function (e) {
            e.preventDefault();
            loadIngestJobDetail(link.getAttribute('data-job-id'));
          });
        }
      })
      .catch(function (err) {
        setUploadError(err.message || 'Upload failed');
      });
  }

  function submitUpload() {
    setUploadError('');
    setUploadSuccess('');
    var file = uploadFileInput && uploadFileInput.files && uploadFileInput.files[0];
    var text = uploadTextarea ? uploadTextarea.value.trim() : '';

    if (file) {
      var reader = new FileReader();
      reader.onload = function () {
        var bytes = new Uint8Array(reader.result);
        var isGzip = isGzipFile(file.name, bytes);
        var b64 = arrayBufferToBase64(reader.result);
        doUpload(b64, isGzip ? 'gzip' : 'none');
      };
      reader.onerror = function () {
        setUploadError('Failed to read file');
      };
      reader.readAsArrayBuffer(file);
    } else if (text) {
      var b64 = btoa(unescape(encodeURIComponent(text)));
      doUpload(b64, 'none');
    } else {
      setUploadError('Paste XML or select a file');
    }
  }

  var currentSearchPage = 1;
  var currentSearchPageSize = 50;

  function setSearchError(msg) {
    if (searchFormError) {
      searchFormError.textContent = msg || '';
      searchFormError.classList.toggle('hidden', !msg);
    }
  }

  function getSearchStateFromHash() {
    var hash = window.location.hash;
    if (!hash || hash.indexOf('#search?') !== 0) return null;
    var params = new URLSearchParams(hash.substring(8));
    return {
      report_type: params.get('report_type') || 'aggregate',
      domains: params.get('domains') ? params.get('domains').split(',') : [],
      query: params.get('query') || '',
      from: params.get('from') || '',
      to: params.get('to') || '',
      include_spf: params.get('include_spf') || '',
      include_dkim: params.get('include_dkim') || '',
      include_disposition: params.get('include_disposition') || '',
      exclude_spf: params.get('exclude_spf') || '',
      exclude_dkim: params.get('exclude_dkim') || '',
      exclude_disposition: params.get('exclude_disposition') || '',
      page: parseInt(params.get('page'), 10) || 1
    };
  }

  function setSearchStateInHash(state) {
    var params = new URLSearchParams();
    if (state.report_type && state.report_type !== 'aggregate') params.set('report_type', state.report_type);
    if (state.domains && state.domains.length) params.set('domains', state.domains.join(','));
    if (state.query) params.set('query', state.query);
    if (state.from) params.set('from', state.from);
    if (state.to) params.set('to', state.to);
    if (state.report_type !== 'forensic') {
      if (state.include_spf) params.set('include_spf', state.include_spf);
      if (state.include_dkim) params.set('include_dkim', state.include_dkim);
      if (state.include_disposition) params.set('include_disposition', state.include_disposition);
      if (state.exclude_spf) params.set('exclude_spf', state.exclude_spf);
      if (state.exclude_dkim) params.set('exclude_dkim', state.exclude_dkim);
      if (state.exclude_disposition) params.set('exclude_disposition', state.exclude_disposition);
    }
    if (state.page && state.page > 1) params.set('page', state.page.toString());
    var qs = params.toString();
    window.location.hash = qs ? 'search?' + qs : 'search';
  }

  function updateAggregateFiltersVisibility() {
    var reportTypeSelect = document.getElementById('search-report-type');
    var aggregateFilters = document.getElementById('search-aggregate-filters');
    if (reportTypeSelect && aggregateFilters) {
      aggregateFilters.style.display = reportTypeSelect.value === 'forensic' ? 'none' : '';
    }
  }

  function loadSearchPage(runFromHash) {
    if (!searchDomainsFieldset || !searchResultsWrap) return;
    setSearchError('');
    if (searchResultsWrap) searchResultsWrap.innerHTML = '';
    if (searchPagination) searchPagination.innerHTML = '';

    var reportTypeSelect = document.getElementById('search-report-type');
    if (reportTypeSelect) {
      reportTypeSelect.removeEventListener('change', updateAggregateFiltersVisibility);
      reportTypeSelect.addEventListener('change', updateAggregateFiltersVisibility);
    }

    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var domains = data.domains || [];
        var hashState = runFromHash ? getSearchStateFromHash() : null;
        var checkedDomains = hashState ? hashState.domains : [];
        searchDomainsFieldset.innerHTML = domains.length
          ? domains.map(function (d) {
              var checked = checkedDomains.indexOf(d.name) >= 0 ? ' checked' : '';
              return '<label><input type="checkbox" name="search_domain" value="' + escapeHtml(d.name) + '"' + checked + '> ' + escapeHtml(d.name) + '</label>';
            }).join('')
          : '<em>No domains available.</em>';
        if (hashState) {
          if (reportTypeSelect) reportTypeSelect.value = hashState.report_type || 'aggregate';
          updateAggregateFiltersVisibility();
          document.getElementById('search-query').value = hashState.query || '';
          if (hashState.from) document.getElementById('search-from').value = hashState.from;
          if (hashState.to) document.getElementById('search-to').value = hashState.to;
          document.getElementById('search-include-spf').value = hashState.include_spf || '';
          document.getElementById('search-include-dkim').value = hashState.include_dkim || '';
          document.getElementById('search-include-disposition').value = hashState.include_disposition || '';
          document.getElementById('search-exclude-spf').value = hashState.exclude_spf || '';
          document.getElementById('search-exclude-dkim').value = hashState.exclude_dkim || '';
          document.getElementById('search-exclude-disposition').value = hashState.exclude_disposition || '';
          currentSearchPage = hashState.page || 1;
          doSearch();
        } else {
          updateAggregateFiltersVisibility();
        }
      })
      .catch(function () { searchDomainsFieldset.innerHTML = '<em>Error loading domains.</em>'; });
  }

  function buildSearchBody() {
    var selectedDomains = Array.from(searchDomainsFieldset.querySelectorAll('input[name=search_domain]:checked')).map(function (c) { return c.value; });
    var queryVal = document.getElementById('search-query').value || '';
    var fromVal = document.getElementById('search-from').value || '';
    var toVal = document.getElementById('search-to').value || '';
    var includeSpf = document.getElementById('search-include-spf').value;
    var includeDkim = document.getElementById('search-include-dkim').value;
    var includeDisposition = document.getElementById('search-include-disposition').value;
    var excludeSpf = document.getElementById('search-exclude-spf').value;
    var excludeDkim = document.getElementById('search-exclude-dkim').value;
    var excludeDisposition = document.getElementById('search-exclude-disposition').value;

    var body = { page: currentSearchPage, page_size: currentSearchPageSize };
    if (selectedDomains.length) body.domains = selectedDomains;
    if (queryVal.trim()) body.query = queryVal.trim();
    if (fromVal) body.from = fromVal;
    if (toVal) body.to = toVal;

    var include = {};
    if (includeSpf) include.spf_result = [includeSpf];
    if (includeDkim) include.dkim_result = [includeDkim];
    if (includeDisposition) include.disposition = [includeDisposition];
    if (Object.keys(include).length) body.include = include;

    var exclude = {};
    if (excludeSpf) exclude.spf_result = [excludeSpf];
    if (excludeDkim) exclude.dkim_result = [excludeDkim];
    if (excludeDisposition) exclude.disposition = [excludeDisposition];
    if (Object.keys(exclude).length) body.exclude = exclude;

    return body;
  }

  function getSelectedReportType() {
    var reportTypeSelect = document.getElementById('search-report-type');
    return reportTypeSelect ? reportTypeSelect.value : 'aggregate';
  }

  function doSearch() {
    setSearchError('');
    if (searchResultsWrap) searchResultsWrap.innerHTML = '<p>Searching…</p>';
    if (searchPagination) searchPagination.innerHTML = '';

    var reportType = getSelectedReportType();
    var body = buildSearchBody();

    var hashState = {
      report_type: reportType,
      domains: body.domains || [],
      query: body.query || '',
      from: body.from || '',
      to: body.to || '',
      include_spf: body.include && body.include.spf_result ? body.include.spf_result[0] : '',
      include_dkim: body.include && body.include.dkim_result ? body.include.dkim_result[0] : '',
      include_disposition: body.include && body.include.disposition ? body.include.disposition[0] : '',
      exclude_spf: body.exclude && body.exclude.spf_result ? body.exclude.spf_result[0] : '',
      exclude_dkim: body.exclude && body.exclude.dkim_result ? body.exclude.dkim_result[0] : '',
      exclude_disposition: body.exclude && body.exclude.disposition ? body.exclude.disposition[0] : '',
      page: currentSearchPage
    };
    setSearchStateInHash(hashState);

    if (reportType === 'forensic') {
      doForensicSearch(body);
    } else {
      doAggregateSearch(body);
    }
  }

  function doAggregateSearch(body) {
    fetch('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify(body),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (!r.ok) {
          setSearchError('Search failed');
          searchResultsWrap.innerHTML = '';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        renderAggregateResults(data);
      })
      .catch(function () {
        setSearchError('Search failed');
        searchResultsWrap.innerHTML = '';
      });
  }

  function doForensicSearch(body) {
    var params = new URLSearchParams();
    if (body.domains && body.domains.length) params.set('domains', body.domains.join(','));
    if (body.from) params.set('from', body.from);
    if (body.to) params.set('to', body.to);
    params.set('page', currentSearchPage.toString());
    params.set('page_size', currentSearchPageSize.toString());

    fetch('/api/v1/reports/forensic?' + params.toString(), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) {
          setSearchError('Search failed');
          searchResultsWrap.innerHTML = '';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        renderForensicResults(data);
      })
      .catch(function () {
        setSearchError('Search failed');
        searchResultsWrap.innerHTML = '';
      });
  }

  function renderAggregateResults(data) {
    var items = data.items || [];
    var total = data.total || 0;
    var page = data.page || 1;
    var pageSize = data.page_size || currentSearchPageSize;
    var totalPages = Math.ceil(total / pageSize) || 1;

    if (!items.length) {
      searchResultsWrap.innerHTML = '<p><em>No results found.</em></p>';
      searchPagination.innerHTML = '';
      return;
    }

    searchResultsWrap.innerHTML = '<p>' + total + ' result' + (total === 1 ? '' : 's') + ' found.</p>' +
      '<table><thead><tr><th>Source IP</th><th>Count</th><th>Disposition</th><th>DKIM</th><th>SPF</th><th>Domain</th><th>Org</th><th></th></tr></thead><tbody>' +
      items.map(function (r) {
        return '<tr>' +
          '<td>' + escapeHtml(r.source_ip || '') + '</td>' +
          '<td>' + (r.count || 0) + '</td>' +
          '<td>' + escapeHtml(r.disposition || '') + '</td>' +
          '<td>' + escapeHtml(r.dkim_result || '') + '</td>' +
          '<td>' + escapeHtml(r.spf_result || '') + '</td>' +
          '<td>' + escapeHtml(r.domain || '') + '</td>' +
          '<td>' + escapeHtml(r.org_name || '') + '</td>' +
          '<td><span class="report-link" data-report-id="' + escapeHtml(r.aggregate_report_id || '') + '">View</span></td>' +
        '</tr>';
      }).join('') + '</tbody></table>';

    searchResultsWrap.querySelectorAll('.report-link').forEach(function (el) {
      el.addEventListener('click', function () {
        var reportId = el.getAttribute('data-report-id');
        if (reportId) showReportDetailModal(reportId);
      });
    });

    renderSearchPagination(page, totalPages);
  }

  function renderForensicResults(data) {
    var items = data.items || [];
    var total = data.total || 0;
    var page = data.page || 1;
    var pageSize = data.page_size || currentSearchPageSize;
    var totalPages = Math.ceil(total / pageSize) || 1;

    if (!items.length) {
      searchResultsWrap.innerHTML = '<p><em>No forensic reports found.</em></p>';
      searchPagination.innerHTML = '';
      return;
    }

    searchResultsWrap.innerHTML = '<p>' + total + ' forensic report' + (total === 1 ? '' : 's') + ' found.</p>' +
      '<table><thead><tr><th>Domain</th><th>Source IP</th><th>Header From</th><th>SPF</th><th>DKIM</th><th>DMARC</th><th>Failure</th><th>Arrival</th><th></th></tr></thead><tbody>' +
      items.map(function (r) {
        return '<tr>' +
          '<td>' + escapeHtml(r.domain || '') + '</td>' +
          '<td>' + escapeHtml(r.source_ip || '') + '</td>' +
          '<td>' + escapeHtml(r.header_from || '') + '</td>' +
          '<td>' + escapeHtml(r.spf_result || '') + '</td>' +
          '<td>' + escapeHtml(r.dkim_result || '') + '</td>' +
          '<td>' + escapeHtml(r.dmarc_result || '') + '</td>' +
          '<td>' + escapeHtml(r.failure_type || '') + '</td>' +
          '<td>' + escapeHtml(r.arrival_time || '') + '</td>' +
          '<td><span class="forensic-report-link" data-report-id="' + escapeHtml(r.id || '') + '">View</span></td>' +
        '</tr>';
      }).join('') + '</tbody></table>';

    searchResultsWrap.querySelectorAll('.forensic-report-link').forEach(function (el) {
      el.addEventListener('click', function () {
        var reportId = el.getAttribute('data-report-id');
        if (reportId) showForensicDetailModal(reportId);
      });
    });

    renderSearchPagination(page, totalPages);
  }

  function renderSearchPagination(page, totalPages) {
    if (totalPages > 1) {
      var paginationHtml = '<p>Page ' + page + ' of ' + totalPages + ' ';
      if (page > 1) paginationHtml += '<a href="#" id="search-prev-page">← Prev</a> ';
      if (page < totalPages) paginationHtml += '<a href="#" id="search-next-page">Next →</a>';
      paginationHtml += '</p>';
      searchPagination.innerHTML = paginationHtml;

      var prevLink = document.getElementById('search-prev-page');
      var nextLink = document.getElementById('search-next-page');
      if (prevLink) {
        prevLink.addEventListener('click', function (e) {
          e.preventDefault();
          currentSearchPage = Math.max(1, currentSearchPage - 1);
          doSearch();
        });
      }
      if (nextLink) {
        nextLink.addEventListener('click', function (e) {
          e.preventDefault();
          currentSearchPage = currentSearchPage + 1;
          doSearch();
        });
      }
    } else {
      searchPagination.innerHTML = '';
    }
  }

  function setLoginError(msg) {
    loginError.textContent = msg || '';
    loginError.classList.toggle('hidden', !msg);
  }

  function setDomainError(msg) {
    domainError.textContent = msg || '';
    domainError.classList.toggle('hidden', !msg);
  }

  function fetchMe() {
    return fetch('/api/v1/auth/me', { credentials: 'same-origin' });
  }

  function fetchDomains() {
    return fetch('/api/v1/domains', { credentials: 'same-origin' });
  }

  function renderDomains(domains, isSuperAdmin) {
    if (!domains.length) {
      domainsList.innerHTML = '<li><em>No domains</em></li>';
      return;
    }
    domainsList.innerHTML = domains.map(function (d) {
      var html = '<li>' + escapeHtml(d.name) + ' <small>(' + d.status + ')</small>';
      if (d.status === 'archived' && d.retention_delete_at) {
        var paused = d.retention_paused ? ' (paused)' : '';
        html += ' <small>retention until ' + escapeHtml(d.retention_delete_at.substring(0, 10)) + paused + '</small>';
      }
      if (isSuperAdmin) {
        if (d.status === 'active') {
          html += ' <button type="button" class="domain-archive-btn" data-domain-id="' + escapeHtml(d.id) + '" data-domain-name="' + escapeHtml(d.name) + '">Archive</button>';
        } else if (d.status === 'archived') {
          html += ' <button type="button" class="domain-restore-btn" data-domain-id="' + escapeHtml(d.id) + '">Restore</button>';
          html += ' <button type="button" class="domain-delete-btn" data-domain-id="' + escapeHtml(d.id) + '" data-domain-name="' + escapeHtml(d.name) + '">Delete</button>';
          html += ' <button type="button" class="domain-stats-btn" data-domain-id="' + escapeHtml(d.id) + '" data-domain-name="' + escapeHtml(d.name) + '">Stats</button>';
          if (d.retention_delete_at && !d.retention_paused) {
            html += ' <button type="button" class="domain-pause-btn" data-domain-id="' + escapeHtml(d.id) + '">Pause retention</button>';
          } else if (d.retention_delete_at && d.retention_paused) {
            html += ' <button type="button" class="domain-unpause-btn" data-domain-id="' + escapeHtml(d.id) + '">Unpause retention</button>';
          }
          var retentionLabel = d.retention_days ? 'Update retention' : 'Set retention';
          html += ' <button type="button" class="domain-set-retention-btn" data-domain-id="' + escapeHtml(d.id) + '" data-domain-name="' + escapeHtml(d.name) + '" data-current-retention="' + (d.retention_days || '') + '">' + retentionLabel + '</button>';
        }
      }
      html += '</li>';
      return html;
    }).join('');
    bindDomainActionButtons();
  }

  function bindDomainActionButtons() {
    domainsList.querySelectorAll('.domain-archive-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openArchiveForm(btn.getAttribute('data-domain-id'), btn.getAttribute('data-domain-name'));
      });
    });
    domainsList.querySelectorAll('.domain-restore-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        doRestoreDomain(btn.getAttribute('data-domain-id'));
      });
    });
    domainsList.querySelectorAll('.domain-delete-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        doDeleteDomain(btn.getAttribute('data-domain-id'), btn.getAttribute('data-domain-name'));
      });
    });
    domainsList.querySelectorAll('.domain-pause-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        doPauseRetention(btn.getAttribute('data-domain-id'));
      });
    });
    domainsList.querySelectorAll('.domain-unpause-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        doUnpauseRetention(btn.getAttribute('data-domain-id'));
      });
    });
    domainsList.querySelectorAll('.domain-set-retention-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openSetRetentionForm(btn.getAttribute('data-domain-id'), btn.getAttribute('data-domain-name'), btn.getAttribute('data-current-retention'));
      });
    });
    domainsList.querySelectorAll('.domain-stats-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        showDomainStats(btn.getAttribute('data-domain-id'), btn.getAttribute('data-domain-name'));
      });
    });
  }

  function showDomainStats(domainId, domainName) {
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/stats', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) return r.json().then(function (d) { throw new Error(d.detail || 'Error'); });
        return r.json();
      })
      .then(function (stats) {
        alert(
          'Stats for ' + domainName + ':\n\n' +
          'Aggregate reports: ' + stats.aggregate_reports + '\n' +
          'Forensic reports: ' + stats.forensic_reports + '\n' +
          'Aggregate records: ' + stats.aggregate_records
        );
      })
      .catch(function (e) {
        alert('Failed to load stats: ' + e.message);
      });
  }

  function openArchiveForm(domainId, domainName) {
    var form = document.getElementById('archive-domain-form');
    var nameEl = document.getElementById('archive-domain-name');
    var idEl = document.getElementById('archive-domain-id');
    var retentionEl = document.getElementById('archive-retention-days');
    var errEl = document.getElementById('archive-domain-error');
    if (!form) return;
    nameEl.textContent = domainName;
    idEl.value = domainId;
    retentionEl.value = '';
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    form.classList.remove('hidden');
  }

  function hideArchiveForm() {
    var form = document.getElementById('archive-domain-form');
    if (form) form.classList.add('hidden');
  }

  function openSetRetentionForm(domainId, domainName, currentRetention) {
    var form = document.getElementById('set-retention-form');
    var nameEl = document.getElementById('set-retention-domain-name');
    var idEl = document.getElementById('set-retention-domain-id');
    var daysEl = document.getElementById('set-retention-days');
    var errEl = document.getElementById('set-retention-error');
    if (!form) return;
    nameEl.textContent = domainName;
    idEl.value = domainId;
    daysEl.value = currentRetention || '';
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    form.classList.remove('hidden');
  }

  function hideSetRetentionForm() {
    var form = document.getElementById('set-retention-form');
    if (form) form.classList.add('hidden');
  }

  function doSetRetention(domainId, retentionDays) {
    var errEl = document.getElementById('set-retention-error');
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    var days = parseInt(retentionDays, 10);
    if (!days || days <= 0) {
      if (errEl) { errEl.textContent = 'Retention days must be > 0'; errEl.classList.remove('hidden'); }
      return;
    }
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/retention', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify({ retention_days: days })
    })
      .then(function (r) {
        if (r.ok) {
          hideSetRetentionForm();
          loadDomains();
        } else {
          return r.json().then(function (d) {
            if (errEl) { errEl.textContent = d.detail || 'Failed to set retention'; errEl.classList.remove('hidden'); }
          });
        }
      })
      .catch(function () { if (errEl) { errEl.textContent = 'Failed to set retention'; errEl.classList.remove('hidden'); } });
  }

  function doArchiveDomain(domainId, retentionDays) {
    var errEl = document.getElementById('archive-domain-error');
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    var body = {};
    if (retentionDays && parseInt(retentionDays, 10) > 0) {
      body.retention_days = parseInt(retentionDays, 10);
    }
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/archive', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify(body),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          hideArchiveForm();
          fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (errEl) { errEl.textContent = d.detail || 'Archive failed'; errEl.classList.remove('hidden'); }
        });
      })
      .catch(function () { if (errEl) { errEl.textContent = 'Archive failed'; errEl.classList.remove('hidden'); } });
  }

  function doRestoreDomain(domainId) {
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/restore', {
      method: 'POST',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          alert(d.detail || 'Restore failed');
        });
      })
      .catch(function () { alert('Restore failed'); });
  }

  function doDeleteDomain(domainId, domainName) {
    if (!confirm('Permanently delete domain "' + domainName + '"? This cannot be undone and will remove all related data.')) return;
    fetch('/api/v1/domains/' + encodeURIComponent(domainId), {
      method: 'DELETE',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 204) {
          fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          alert(d.detail || 'Delete failed');
        });
      })
      .catch(function () { alert('Delete failed'); });
  }

  function doPauseRetention(domainId) {
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/retention/pause', {
      method: 'POST',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          alert(d.detail || 'Pause failed');
        });
      })
      .catch(function () { alert('Pause failed'); });
  }

  function doUnpauseRetention(domainId) {
    fetch('/api/v1/domains/' + encodeURIComponent(domainId) + '/retention/unpause', {
      method: 'POST',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          alert(d.detail || 'Unpause failed');
        });
      })
      .catch(function () { alert('Unpause failed'); });
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function showReportDetailModal(reportId) {
    if (!reportDetailModal) return;
    reportDetailTitle.textContent = 'Loading...';
    reportDetailSummary.innerHTML = '';
    reportDetailRecords.innerHTML = '<p>Loading...</p>';
    reportDetailModal.classList.remove('hidden');

    fetch('/api/v1/reports/aggregate/' + encodeURIComponent(reportId), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) {
          reportDetailTitle.textContent = 'Error';
          reportDetailRecords.innerHTML = '<p class="error">Failed to load report.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        reportDetailTitle.textContent = 'Report: ' + escapeHtml(data.report_id || data.id);
        var beginDate = data.date_begin ? new Date(data.date_begin * 1000).toISOString().split('T')[0] : '';
        var endDate = data.date_end ? new Date(data.date_end * 1000).toISOString().split('T')[0] : '';
        reportDetailSummary.innerHTML =
          '<p><strong>Organization:</strong> ' + escapeHtml(data.org_name || '') + '</p>' +
          '<p><strong>Domain:</strong> ' + escapeHtml(data.domain || '') + '</p>' +
          '<p><strong>Date range:</strong> ' + escapeHtml(beginDate) + ' to ' + escapeHtml(endDate) + '</p>';
        var records = data.records || [];
        if (!records.length) {
          reportDetailRecords.innerHTML = '<p><em>No records in this report.</em></p>';
          return;
        }
        reportDetailRecords.innerHTML =
          '<table><thead><tr><th>Source IP</th><th>Count</th><th>Disposition</th><th>DKIM</th><th>SPF</th><th>Header From</th><th>Envelope From</th><th>Envelope To</th></tr></thead><tbody>' +
          records.map(function (r) {
            return '<tr>' +
              '<td>' + escapeHtml(r.source_ip || '') + '</td>' +
              '<td>' + (r.count || 0) + '</td>' +
              '<td>' + escapeHtml(r.disposition || '') + '</td>' +
              '<td>' + escapeHtml(r.dkim_result || '') + '</td>' +
              '<td>' + escapeHtml(r.spf_result || '') + '</td>' +
              '<td>' + escapeHtml(r.header_from || '') + '</td>' +
              '<td>' + escapeHtml(r.envelope_from || '') + '</td>' +
              '<td>' + escapeHtml(r.envelope_to || '') + '</td>' +
            '</tr>';
          }).join('') + '</tbody></table>';
      })
      .catch(function () {
        reportDetailTitle.textContent = 'Error';
        reportDetailRecords.innerHTML = '<p class="error">Error loading report.</p>';
      });
  }

  function showForensicDetailModal(reportId) {
    if (!reportDetailModal) return;
    reportDetailTitle.textContent = 'Loading...';
    reportDetailSummary.innerHTML = '';
    reportDetailRecords.innerHTML = '<p>Loading...</p>';
    reportDetailModal.classList.remove('hidden');

    fetch('/api/v1/reports/forensic/' + encodeURIComponent(reportId), { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) {
          reportDetailTitle.textContent = 'Error';
          reportDetailRecords.innerHTML = '<p class="error">Failed to load report.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        reportDetailTitle.textContent = 'Forensic Report: ' + escapeHtml(data.report_id || data.id);
        reportDetailSummary.innerHTML =
          '<p><strong>Organization:</strong> ' + escapeHtml(data.org_name || '') + '</p>' +
          '<p><strong>Domain:</strong> ' + escapeHtml(data.domain || '') + '</p>' +
          '<p><strong>Source IP:</strong> ' + escapeHtml(data.source_ip || '') + '</p>' +
          '<p><strong>Arrival time:</strong> ' + escapeHtml(data.arrival_time || '') + '</p>' +
          '<p><strong>Header from:</strong> ' + escapeHtml(data.header_from || '') + '</p>' +
          '<p><strong>Envelope from:</strong> ' + escapeHtml(data.envelope_from || '') + '</p>' +
          '<p><strong>Envelope to:</strong> ' + escapeHtml(data.envelope_to || '') + '</p>';
        reportDetailRecords.innerHTML =
          '<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>' +
          '<tr><td>SPF result</td><td>' + escapeHtml(data.spf_result || '') + '</td></tr>' +
          '<tr><td>DKIM result</td><td>' + escapeHtml(data.dkim_result || '') + '</td></tr>' +
          '<tr><td>DMARC result</td><td>' + escapeHtml(data.dmarc_result || '') + '</td></tr>' +
          '<tr><td>Failure type</td><td>' + escapeHtml(data.failure_type || '') + '</td></tr>' +
          '</tbody></table>';
      })
      .catch(function () {
        reportDetailTitle.textContent = 'Error';
        reportDetailRecords.innerHTML = '<p class="error">Error loading report.</p>';
      });
  }

  function hideReportDetailModal() {
    if (reportDetailModal) reportDetailModal.classList.add('hidden');
  }

  function loadDomainsPage(meData) {
    var isSuperAdmin = meData.user.role === 'super-admin';
    userInfo.textContent = 'Logged in as ' + escapeHtml(meData.user.username) + ' (' + meData.user.role + ')';
    hideArchiveForm();
    hideSetRetentionForm();
    if (isSuperAdmin) {
      addDomainForm.classList.remove('hidden');
      if (auditLinkWrap) auditLinkWrap.innerHTML = '· <a href="#" id="link-audit">Audit</a>';
    } else {
      addDomainForm.classList.add('hidden');
      if (auditLinkWrap) auditLinkWrap.innerHTML = '';
    }
    if (meData.user.role === 'admin' || isSuperAdmin) {
      if (apikeysLinkWrap) apikeysLinkWrap.innerHTML = '· <a href="#" id="link-apikeys">API keys</a>';
      if (usersLinkWrap) usersLinkWrap.innerHTML = '· <a href="#" id="link-users">Users</a>';
    } else {
      if (apikeysLinkWrap) apikeysLinkWrap.innerHTML = '';
      if (usersLinkWrap) usersLinkWrap.innerHTML = '';
    }
    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) { renderDomains(data.domains || [], isSuperAdmin); })
      .catch(function () { renderDomains([], false); });
  }

  function fetchDashboards() {
    return fetch('/api/v1/dashboards', { credentials: 'same-origin' });
  }

  function loadDashboardsPage() {
    fetchDashboards()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        const list = data.dashboards || [];
        dashboardsList.innerHTML = list.length
          ? list.map(function (d) { return '<li><a href="#" data-dashboard-id="' + escapeHtml(d.id) + '">' + escapeHtml(d.name) + '</a></li>'; }).join('')
          : '<li><em>No dashboards</em></li>';
        dashboardsList.querySelectorAll('a[data-dashboard-id]').forEach(function (a) {
          a.addEventListener('click', function (e) {
            e.preventDefault();
            loadDashboardDetail(a.getAttribute('data-dashboard-id'));
          });
        });
      })
      .catch(function () { dashboardsList.innerHTML = '<li><em>Error loading dashboards</em></li>'; });
    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        const domains = data.domains || [];
        dashboardDomainsFieldset.innerHTML = domains.length
          ? domains.map(function (d) { return '<label><input type="checkbox" name="domain_id" value="' + escapeHtml(d.id) + '"> ' + escapeHtml(d.name) + '</label>'; }).join('')
          : '<em>No domains. Add domains first.</em>';
      });
  }

  function getDashboardStateFromHash() {
    var hash = window.location.hash;
    if (!hash || hash.indexOf('#dashboard/') !== 0) return null;
    var rest = hash.substring(11);
    var qmark = rest.indexOf('?');
    var dashId = qmark >= 0 ? rest.substring(0, qmark) : rest;
    var params = qmark >= 0 ? new URLSearchParams(rest.substring(qmark + 1)) : new URLSearchParams();
    return {
      dashboard_id: dashId,
      from: params.get('from') || '',
      to: params.get('to') || '',
      include_spf: params.get('include_spf') || '',
      include_dkim: params.get('include_dkim') || '',
      include_disposition: params.get('include_disposition') || '',
      exclude_spf: params.get('exclude_spf') || '',
      exclude_dkim: params.get('exclude_dkim') || '',
      exclude_disposition: params.get('exclude_disposition') || '',
      page: parseInt(params.get('page'), 10) || 1
    };
  }

  function setDashboardStateInHash(dashId, state) {
    var params = new URLSearchParams();
    if (state.from) params.set('from', state.from);
    if (state.to) params.set('to', state.to);
    if (state.include_spf) params.set('include_spf', state.include_spf);
    if (state.include_dkim) params.set('include_dkim', state.include_dkim);
    if (state.include_disposition) params.set('include_disposition', state.include_disposition);
    if (state.exclude_spf) params.set('exclude_spf', state.exclude_spf);
    if (state.exclude_dkim) params.set('exclude_dkim', state.exclude_dkim);
    if (state.exclude_disposition) params.set('exclude_disposition', state.exclude_disposition);
    if (state.page && state.page > 1) params.set('page', state.page.toString());
    var qs = params.toString();
    window.location.hash = qs ? 'dashboard/' + dashId + '?' + qs : 'dashboard/' + dashId;
  }

  function buildDashboardFilterBody(domainNames) {
    var fromVal = document.getElementById('dashboard-from').value || '';
    var toVal = document.getElementById('dashboard-to').value || '';
    var includeSpf = document.getElementById('dashboard-include-spf').value;
    var includeDkim = document.getElementById('dashboard-include-dkim').value;
    var includeDisposition = document.getElementById('dashboard-include-disposition').value;
    var excludeSpf = document.getElementById('dashboard-exclude-spf').value;
    var excludeDkim = document.getElementById('dashboard-exclude-dkim').value;
    var excludeDisposition = document.getElementById('dashboard-exclude-disposition').value;

    var body = { domains: domainNames, page: currentDashboardPage, page_size: currentDashboardPageSize };
    if (fromVal) body.from = fromVal;
    if (toVal) body.to = toVal;

    var include = {};
    if (includeSpf) include.spf_result = [includeSpf];
    if (includeDkim) include.dkim_result = [includeDkim];
    if (includeDisposition) include.disposition = [includeDisposition];
    if (Object.keys(include).length) body.include = include;

    var exclude = {};
    if (excludeSpf) exclude.spf_result = [excludeSpf];
    if (excludeDkim) exclude.dkim_result = [excludeDkim];
    if (excludeDisposition) exclude.disposition = [excludeDisposition];
    if (Object.keys(exclude).length) body.exclude = exclude;

    return body;
  }

  function doDashboardFilter() {
    if (!currentDashboardData) return;
    var domainNames = currentDashboardData.domain_names || [];
    if (!domainNames.length) {
      dashboardWidget.innerHTML = '<p>No domains in this dashboard.</p>';
      return;
    }

    var body = buildDashboardFilterBody(domainNames);
    var hashState = {
      from: body.from || '',
      to: body.to || '',
      include_spf: body.include && body.include.spf_result ? body.include.spf_result[0] : '',
      include_dkim: body.include && body.include.dkim_result ? body.include.dkim_result[0] : '',
      include_disposition: body.include && body.include.disposition ? body.include.disposition[0] : '',
      exclude_spf: body.exclude && body.exclude.spf_result ? body.exclude.spf_result[0] : '',
      exclude_dkim: body.exclude && body.exclude.dkim_result ? body.exclude.dkim_result[0] : '',
      exclude_disposition: body.exclude && body.exclude.disposition ? body.exclude.disposition[0] : '',
      page: currentDashboardPage
    };
    setDashboardStateInHash(currentDashboardId, hashState);

    dashboardWidget.innerHTML = '<p>Loading…</p>';
    var paginationEl = document.getElementById('dashboard-pagination');
    if (paginationEl) paginationEl.innerHTML = '';

    fetch('/api/v1/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify(body),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (!r.ok) {
          dashboardWidget.innerHTML = '<p class="error">Failed to load data</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        renderDashboardResults(data);
      })
      .catch(function () {
        dashboardWidget.innerHTML = '<p class="error">Error loading data</p>';
      });
  }

  function renderDashboardResults(data) {
    var items = data.items || [];
    var total = data.total || 0;
    var page = data.page || 1;
    var pageSize = data.page_size || currentDashboardPageSize;
    var totalPages = Math.ceil(total / pageSize) || 1;

    if (!items.length) {
      dashboardWidget.innerHTML = '<p><em>No results found.</em></p>';
      var paginationEl = document.getElementById('dashboard-pagination');
      if (paginationEl) paginationEl.innerHTML = '';
      return;
    }

    dashboardWidget.innerHTML = '<p>' + total + ' result' + (total === 1 ? '' : 's') + ' found.</p>' +
      '<table><thead><tr><th>Source IP</th><th>Count</th><th>Disposition</th><th>DKIM</th><th>SPF</th><th>Domain</th><th>Org</th><th></th></tr></thead><tbody>' +
      items.map(function (r) {
        return '<tr>' +
          '<td>' + escapeHtml(r.source_ip || '') + '</td>' +
          '<td>' + (r.count || 0) + '</td>' +
          '<td>' + escapeHtml(r.disposition || '') + '</td>' +
          '<td>' + escapeHtml(r.dkim_result || '') + '</td>' +
          '<td>' + escapeHtml(r.spf_result || '') + '</td>' +
          '<td>' + escapeHtml(r.domain || '') + '</td>' +
          '<td>' + escapeHtml(r.org_name || '') + '</td>' +
          '<td><span class="report-link" data-report-id="' + escapeHtml(r.aggregate_report_id || '') + '">View</span></td>' +
        '</tr>';
      }).join('') + '</tbody></table>';

    dashboardWidget.querySelectorAll('.report-link').forEach(function (el) {
      el.addEventListener('click', function () {
        var reportId = el.getAttribute('data-report-id');
        if (reportId) showReportDetailModal(reportId);
      });
    });

    renderDashboardPagination(page, totalPages);
  }

  function renderDashboardPagination(page, totalPages) {
    var paginationEl = document.getElementById('dashboard-pagination');
    if (!paginationEl) return;
    if (totalPages > 1) {
      var html = '<p>Page ' + page + ' of ' + totalPages + ' ';
      if (page > 1) html += '<a href="#" id="dashboard-prev-page">← Prev</a> ';
      if (page < totalPages) html += '<a href="#" id="dashboard-next-page">Next →</a>';
      html += '</p>';
      paginationEl.innerHTML = html;

      var prevLink = document.getElementById('dashboard-prev-page');
      var nextLink = document.getElementById('dashboard-next-page');
      if (prevLink) {
        prevLink.addEventListener('click', function (e) {
          e.preventDefault();
          currentDashboardPage = Math.max(1, currentDashboardPage - 1);
          doDashboardFilter();
        });
      }
      if (nextLink) {
        nextLink.addEventListener('click', function (e) {
          e.preventDefault();
          currentDashboardPage = currentDashboardPage + 1;
          doDashboardFilter();
        });
      }
    } else {
      paginationEl.innerHTML = '';
    }
  }

  function populateDashboardFiltersFromState(state) {
    if (state.from) document.getElementById('dashboard-from').value = state.from;
    if (state.to) document.getElementById('dashboard-to').value = state.to;
    document.getElementById('dashboard-include-spf').value = state.include_spf || '';
    document.getElementById('dashboard-include-dkim').value = state.include_dkim || '';
    document.getElementById('dashboard-include-disposition').value = state.include_disposition || '';
    document.getElementById('dashboard-exclude-spf').value = state.exclude_spf || '';
    document.getElementById('dashboard-exclude-dkim').value = state.exclude_dkim || '';
    document.getElementById('dashboard-exclude-disposition').value = state.exclude_disposition || '';
    currentDashboardPage = state.page || 1;
  }

  function resetDashboardFilters() {
    document.getElementById('dashboard-from').value = '';
    document.getElementById('dashboard-to').value = '';
    document.getElementById('dashboard-include-spf').value = '';
    document.getElementById('dashboard-include-dkim').value = '';
    document.getElementById('dashboard-include-disposition').value = '';
    document.getElementById('dashboard-exclude-spf').value = '';
    document.getElementById('dashboard-exclude-dkim').value = '';
    document.getElementById('dashboard-exclude-disposition').value = '';
    currentDashboardPage = 1;
  }

  function loadDashboardDetail(dashId, hashState) {
    currentDashboardId = dashId;
    currentDashboardName = null;
    currentDashboardData = null;
    var exportErr = document.getElementById('dashboard-export-error');
    var actionsEl = document.getElementById('dashboard-detail-actions');
    var editForm = document.getElementById('dashboard-edit-form');
    if (exportErr) { exportErr.textContent = ''; exportErr.classList.add('hidden'); }
    if (actionsEl) actionsEl.innerHTML = '';
    if (editForm) editForm.classList.add('hidden');
    showDashboardDetail();
    dashboardDetailTitle.textContent = 'Loading…';
    dashboardWidget.innerHTML = '';
    Promise.all([
      fetch('/api/v1/dashboards/' + encodeURIComponent(dashId), { credentials: 'same-origin' }),
      fetchMe()
    ])
      .then(function (responses) {
        var dashResp = responses[0];
        var meResp = responses[1];
        if (!dashResp.ok) { dashboardWidget.innerHTML = '<p class="error">Cannot load dashboard</p>'; return Promise.resolve([null, null]); }
        return Promise.all([dashResp.json(), meResp.ok ? meResp.json() : Promise.resolve(null)]);
      })
      .then(function (data) {
        var dash = data[0];
        var meData = data[1];
        if (!dash) return;
        currentDashboardName = dash.name || 'dashboard';
        currentDashboardData = dash;
        currentUserRole = meData && meData.user ? meData.user.role : null;
        dashboardDetailTitle.textContent = dash.name || 'Dashboard';
        if (actionsEl && currentUserRole && currentUserRole !== 'viewer') {
          actionsEl.innerHTML = '· <a href="#" id="link-edit-dashboard">Edit</a> · <a href="#" id="link-delete-dashboard">Delete</a>';
          var editLink = document.getElementById('link-edit-dashboard');
          var deleteLink = document.getElementById('link-delete-dashboard');
          if (editLink) editLink.addEventListener('click', function (e) { e.preventDefault(); openDashboardEditForm(); });
          if (deleteLink) deleteLink.addEventListener('click', function (e) { e.preventDefault(); doDeleteDashboard(); });
        }
        if (hashState) {
          populateDashboardFiltersFromState(hashState);
        } else {
          resetDashboardFilters();
        }
        doDashboardFilter();
        loadDashboardShares();
      })
      .catch(function () { dashboardWidget.innerHTML = '<p class="error">Error loading widget data</p>'; });
  }

  function openDashboardEditForm() {
    var form = document.getElementById('dashboard-edit-form');
    var inner = document.getElementById('dashboard-edit-form-inner');
    var fieldset = document.getElementById('dashboard-edit-domains-fieldset');
    var errEl = document.getElementById('dashboard-edit-error');
    if (!form || !inner || !currentDashboardData) return;
    inner.dashboard_id.value = currentDashboardId;
    inner.name.value = currentDashboardData.name || '';
    inner.description.value = currentDashboardData.description || '';
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var domains = data.domains || [];
        var currentIds = currentDashboardData.domain_ids || [];
        if (!domains.length) {
          fieldset.innerHTML = '<em>No domains available.</em>';
        } else {
          fieldset.innerHTML = domains.map(function (d) {
            var checked = currentIds.indexOf(d.id) >= 0 ? ' checked' : '';
            return '<label><input type="checkbox" name="domain_id" value="' + escapeHtml(d.id) + '"' + checked + '> ' + escapeHtml(d.name) + '</label>';
          }).join('');
        }
        form.classList.remove('hidden');
      });
  }

  function hideDashboardEditForm() {
    var form = document.getElementById('dashboard-edit-form');
    if (form) form.classList.add('hidden');
  }

  function doDeleteDashboard() {
    if (!currentDashboardId) return;
    if (!confirm('Delete this dashboard? This cannot be undone.')) return;
    fetch('/api/v1/dashboards/' + encodeURIComponent(currentDashboardId), {
      method: 'DELETE',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 204) {
          showDashboards();
          loadDashboardsPage();
          return;
        }
        if (r.status === 403) {
          alert('Forbidden: You cannot delete this dashboard.');
          return;
        }
        if (r.status === 404) {
          alert('Dashboard not found.');
          return;
        }
        alert('Failed to delete dashboard.');
      })
      .catch(function () { alert('Failed to delete dashboard.'); });
  }

  function loadDashboardShares() {
    var sharingSection = document.getElementById('dashboard-sharing-section');
    var sharesList = document.getElementById('dashboard-shares-list');
    var shareForm = document.getElementById('dashboard-share-form');
    if (!sharingSection || !sharesList || !currentDashboardId) return;
    if (currentUserRole === 'viewer') {
      sharingSection.classList.add('hidden');
      return;
    }
    sharingSection.classList.remove('hidden');
    sharesList.innerHTML = '<p>Loading...</p>';
    fetch('/api/v1/dashboards/' + encodeURIComponent(currentDashboardId) + '/shares', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) {
          sharesList.innerHTML = '<p class="error">Failed to load shares.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        var shares = data.shares || [];
        if (!shares.length) {
          sharesList.innerHTML = '<p><em>Not shared with anyone.</em></p>';
        } else {
          sharesList.innerHTML = '<table><thead><tr><th>User</th><th>Access</th><th></th></tr></thead><tbody>' +
            shares.map(function (s) {
              return '<tr><td>' + escapeHtml(s.username || s.user_id) + '</td><td>' + escapeHtml(s.access_level) + '</td>' +
                '<td><button type="button" class="unshare-btn" data-user-id="' + escapeHtml(s.user_id) + '">Remove</button></td></tr>';
            }).join('') + '</tbody></table>';
          sharesList.querySelectorAll('.unshare-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
              doUnshareDashboard(btn.getAttribute('data-user-id'));
            });
          });
        }
        if (shareForm) {
          shareForm.classList.remove('hidden');
          loadShareUserOptions();
        }
      })
      .catch(function () { sharesList.innerHTML = '<p class="error">Error loading shares.</p>'; });
  }

  function loadShareUserOptions() {
    var select = document.getElementById('share-user-select');
    if (!select) return;
    fetch('/api/v1/users', { credentials: 'same-origin' })
      .then(function (r) {
        if (!r.ok) return { users: [] };
        return r.json();
      })
      .then(function (data) {
        var users = data.users || [];
        select.innerHTML = '<option value="">— select user —</option>' +
          users.map(function (u) {
            return '<option value="' + escapeHtml(u.id) + '">' + escapeHtml(u.username) + ' (' + escapeHtml(u.role) + ')</option>';
          }).join('');
      })
      .catch(function () { select.innerHTML = '<option value="">— error loading users —</option>'; });
  }

  function doShareDashboard(userId, accessLevel) {
    if (!currentDashboardId || !userId) return;
    var errEl = document.getElementById('dashboard-share-error');
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    fetch('/api/v1/dashboards/' + encodeURIComponent(currentDashboardId) + '/share', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ user_id: userId, access_level: accessLevel }),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 201) {
          loadDashboardShares();
          document.getElementById('share-user-select').value = '';
          return;
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (errEl) { errEl.textContent = d.detail || 'Share failed'; errEl.classList.remove('hidden'); }
        });
      })
      .catch(function () { if (errEl) { errEl.textContent = 'Share failed'; errEl.classList.remove('hidden'); } });
  }

  function doUnshareDashboard(userId) {
    if (!currentDashboardId || !userId) return;
    if (!confirm('Remove this user\'s access?')) return;
    fetch('/api/v1/dashboards/' + encodeURIComponent(currentDashboardId) + '/share/' + encodeURIComponent(userId), {
      method: 'DELETE',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 204) {
          loadDashboardShares();
          return;
        }
        if (r.status === 403) {
          alert('Forbidden: You cannot remove this share.');
          return;
        }
        alert('Failed to remove share.');
      })
      .catch(function () { alert('Failed to remove share.'); });
  }

  function setDashboardFormError(msg) {
    dashboardFormError.textContent = msg || '';
    dashboardFormError.classList.toggle('hidden', !msg);
  }

  function doExportDashboard() {
    var errEl = document.getElementById('dashboard-export-error');
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    if (!currentDashboardId) return;
    var slug = (currentDashboardName || 'dashboard').replace(/[^a-zA-Z0-9-_]/g, '-').replace(/-+/g, '-') || 'dashboard';
    fetch('/api/v1/dashboards/' + encodeURIComponent(currentDashboardId) + '/export', { credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 403 || r.status === 404) {
          if (errEl) { errEl.textContent = r.status === 403 ? 'You cannot export this dashboard.' : 'Dashboard not found.'; errEl.classList.remove('hidden'); }
          return;
        }
        if (!r.ok) {
          if (errEl) { errEl.textContent = 'Export failed.'; errEl.classList.remove('hidden'); }
          return;
        }
        return r.text().then(function (yamlStr) {
          var blob = new Blob([yamlStr], { type: 'application/x-yaml' });
          var url = URL.createObjectURL(blob);
          var a = document.createElement('a');
          a.href = url;
          a.download = slug + '.yaml';
          a.click();
          URL.revokeObjectURL(url);
        });
      })
      .catch(function () {
        if (errEl) { errEl.textContent = 'Export failed.'; errEl.classList.remove('hidden'); }
      });
  }

  function parseExportYaml(text) {
    if (!text || !text.trim()) return null;
    var t = text.trim();
    if (t.charAt(0) === '{') {
      try {
        return JSON.parse(t);
      } catch (e) {
        return null;
      }
    }
    var name = '';
    var description = '';
    var domains = [];
    var lines = text.split(/\r?\n/);
    var inDomains = false;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var keyMatch = line.match(/^\s*(\w+):\s*(.*)$/);
      if (keyMatch) {
        inDomains = false;
        var key = keyMatch[1];
        var rest = (keyMatch[2] || '').trim();
        if (key === 'name') name = rest;
        else if (key === 'description') description = rest;
        else if (key === 'domains') inDomains = true;
        continue;
      }
      var listMatch = line.match(/^\s*-\s*(.+)$/);
      if (listMatch && inDomains) domains.push(listMatch[1].trim());
    }
    if (!name && domains.length === 0) return null;
    return { name: name, description: description, domains: domains };
  }

  function renderImportMapping(domainNames, localDomains) {
    var wrap = document.getElementById('import-domain-mapping-wrap');
    if (!wrap) return;
    if (!domainNames.length) {
      wrap.innerHTML = '<p><em>Paste YAML with a <code>domains</code> list to see mapping.</em></p>';
      return;
    }
    var options = localDomains.map(function (d) {
      return '<option value="">— select —</option><option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.name) + '</option>';
    }).join('');
    wrap.innerHTML = '<fieldset><legend>Map each domain to a local domain</legend>' +
      domainNames.map(function (name, idx) {
        return '<label>' + escapeHtml(name) + ' → <select data-import-domain-name="' + escapeHtml(name) + '">' +
          '<option value="">— select —</option>' +
          localDomains.map(function (d) { return '<option value="' + escapeHtml(d.id) + '">' + escapeHtml(d.name) + '</option>'; }).join('') +
          '</select></label>';
      }).join('<br/>') +
      '</fieldset>';
  }

  function updateImportForm() {
    var textarea = document.getElementById('import-yaml-textarea');
    var parseErr = document.getElementById('import-yaml-parse-error');
    if (!textarea || !parseErr) return;
    var parsed = parseExportYaml(textarea.value);
    parseErr.classList.add('hidden');
    parseErr.textContent = '';
    if (!parsed) {
      if (textarea.value.trim()) {
        parseErr.textContent = 'Invalid YAML. Expected name, description, and domains list.';
        parseErr.classList.remove('hidden');
      }
      renderImportMapping([], []);
      return;
    }
    if (!parsed.domains || !parsed.domains.length) {
      renderImportMapping([], []);
      return;
    }
    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderImportMapping(parsed.domains, data.domains || []);
      })
      .catch(function () { renderImportMapping(parsed.domains, []); });
  }

  function doImportDashboard() {
    var textarea = document.getElementById('import-yaml-textarea');
    var errEl = document.getElementById('import-form-error');
    var successEl = document.getElementById('import-form-success');
    if (!textarea || !errEl || !successEl) return;
    errEl.classList.add('hidden');
    successEl.classList.add('hidden');
    errEl.textContent = '';
    successEl.textContent = '';
    var yamlStr = textarea.value.trim();
    var parsed = parseExportYaml(yamlStr);
    if (!parsed || !parsed.domains || !parsed.domains.length) {
      errEl.textContent = 'Invalid YAML or no domains. Paste export YAML with name and domains.';
      errEl.classList.remove('hidden');
      return;
    }
    var wrap = document.getElementById('import-domain-mapping-wrap');
    var domainRemap = {};
    var selects = wrap ? wrap.querySelectorAll('select[data-import-domain-name]') : [];
    for (var i = 0; i < selects.length; i++) {
      var name = selects[i].getAttribute('data-import-domain-name');
      var id = selects[i].value;
      if (name && id) domainRemap[name] = id;
    }
    var missing = parsed.domains.filter(function (n) { return !domainRemap[n]; });
    if (missing.length) {
      errEl.textContent = 'Select a local domain for: ' + missing.join(', ');
      errEl.classList.remove('hidden');
      return;
    }
    fetch('/api/v1/dashboards/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ yaml: yamlStr, domain_remap: domainRemap }),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 201) {
          return r.json().then(function (dash) {
            successEl.innerHTML = 'Dashboard created. <a href="#" data-dashboard-id="' + escapeHtml(dash.id) + '">Open it</a>';
            successEl.classList.remove('hidden');
            loadDashboardsPage();
            successEl.querySelector('a[data-dashboard-id]').addEventListener('click', function (e) {
              e.preventDefault();
              loadDashboardDetail(this.getAttribute('data-dashboard-id'));
            });
          });
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          errEl.textContent = d.detail || 'Import failed';
          errEl.classList.remove('hidden');
        });
      })
      .catch(function () {
        errEl.textContent = 'Import failed';
        errEl.classList.remove('hidden');
      });
  }

  function fetchApikeys() {
    return fetch('/api/v1/apikeys', { credentials: 'same-origin' });
  }

  function loadApikeysPage(keepCreatedMsg) {
    if (!apikeysListWrap) return;
    apikeysListWrap.innerHTML = '<p>Loading…</p>';
    if (!keepCreatedMsg) clearApikeyCreatedMsg();
    fetchApikeys()
      .then(function (r) {
        if (r.status === 403) {
          apikeysListWrap.innerHTML = '<p class="error">You do not have permission to manage API keys.</p>';
          return null;
        }
        if (!r.ok) {
          apikeysListWrap.innerHTML = '<p class="error">Failed to load API keys.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        const keys = data.keys || [];
        if (!keys.length) {
          apikeysListWrap.innerHTML = '<p><em>No API keys.</em></p>';
        } else {
          apikeysListWrap.innerHTML = '<table><thead><tr><th>Nickname</th><th>Description</th><th>Domains</th><th>Scopes</th><th>Created</th><th></th></tr></thead><tbody>' +
            keys.map(function (k) {
              const domains = (k.domain_names || []).join(', ') || (k.domain_ids || []).join(', ');
              const scopes = (k.scopes || []).join(', ');
              return '<tr><td>' + escapeHtml(k.nickname || '') + '</td><td>' + escapeHtml(k.description || '') + '</td><td>' + escapeHtml(domains) + '</td><td>' + escapeHtml(scopes) + '</td><td>' + escapeHtml(k.created_at || '') + '</td><td><button type="button" class="apikey-delete-btn" data-key-id="' + escapeHtml(k.id) + '">Revoke</button></td></tr>';
            }).join('') + '</tbody></table>';
          apikeysListWrap.querySelectorAll('.apikey-delete-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
              var id = btn.getAttribute('data-key-id');
              if (!id) return;
              if (!confirm('Revoke this API key? It will stop working immediately.')) return;
              fetch('/api/v1/apikeys/' + encodeURIComponent(id), { method: 'DELETE', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' })
                .then(function (r) {
                  if (r.status === 204) loadApikeysPage();
                  else if (r.status === 403) alert('Forbidden');
                  else if (r.status === 404) alert('Not found');
                });
            });
          });
        }
        return fetchDomains();
      })
      .then(function (r) {
        if (!r) return;
        return r.json();
      })
      .then(function (domData) {
        var fieldset = document.getElementById('apikey-domains-fieldset');
        if (!fieldset) return;
        var domains = (domData && domData.domains) ? domData.domains : [];
        fieldset.innerHTML = domains.length
          ? domains.map(function (d) { return '<label><input type="checkbox" name="domain_id" value="' + escapeHtml(d.id) + '"> ' + escapeHtml(d.name) + '</label>'; }).join('')
          : '<em>No domains. Add domains first.</em>';
      })
      .catch(function () { apikeysListWrap.innerHTML = '<p class="error">Error loading API keys.</p>'; });
  }

  function clearApikeyCreatedMsg() {
    var msgEl = document.getElementById('apikey-created-msg');
    if (msgEl) { msgEl.textContent = ''; msgEl.classList.add('hidden'); }
  }

  function fetchUsers() {
    return fetch('/api/v1/users', { credentials: 'same-origin' });
  }

  function clearUserCreatedMsg() {
    var msgEl = document.getElementById('user-created-msg');
    if (msgEl) { msgEl.textContent = ''; msgEl.classList.add('hidden'); }
  }

  function hideUserForms() {
    var editForm = document.getElementById('user-edit-form');
    var domainsForm = document.getElementById('user-domains-form');
    if (editForm) editForm.classList.add('hidden');
    if (domainsForm) domainsForm.classList.add('hidden');
  }

  function loadUsersPage(keepCreatedMsg) {
    if (!usersListWrap) return;
    usersListWrap.innerHTML = '<p>Loading…</p>';
    if (!keepCreatedMsg) clearUserCreatedMsg();
    hideUserForms();
    fetchUsers()
      .then(function (r) {
        if (r.status === 403) {
          usersListWrap.innerHTML = '<p class="error">You do not have permission to manage users.</p>';
          return null;
        }
        if (!r.ok) {
          usersListWrap.innerHTML = '<p class="error">Failed to load users.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        var users = data.users || [];
        if (!users.length) {
          usersListWrap.innerHTML = '<p><em>No users.</em></p>';
          return;
        }
        usersListWrap.innerHTML = '<table><thead><tr><th>Username</th><th>Role</th><th>Domains</th><th>Actions</th></tr></thead><tbody>' +
          users.map(function (u) {
            var domainCount = (u.domain_ids || []).length;
            return '<tr>' +
              '<td>' + escapeHtml(u.username || '') + '</td>' +
              '<td>' + escapeHtml(u.role || '') + '</td>' +
              '<td>' + domainCount + ' domain' + (domainCount === 1 ? '' : 's') + '</td>' +
              '<td>' +
                '<button type="button" class="user-edit-btn" data-user-id="' + escapeHtml(u.id) + '" data-username="' + escapeHtml(u.username) + '" data-role="' + escapeHtml(u.role) + '">Edit</button> ' +
                '<button type="button" class="user-reset-btn" data-user-id="' + escapeHtml(u.id) + '" data-username="' + escapeHtml(u.username) + '">Reset password</button> ' +
                '<button type="button" class="user-domains-btn" data-user-id="' + escapeHtml(u.id) + '" data-username="' + escapeHtml(u.username) + '" data-domain-ids="' + escapeHtml((u.domain_ids || []).join(',')) + '">Domains</button> ' +
                (u.id !== meData.user.id ? '<button type="button" class="user-delete-btn" data-user-id="' + escapeHtml(u.id) + '" data-username="' + escapeHtml(u.username) + '">Delete</button>' : '') +
              '</td>' +
            '</tr>';
          }).join('') + '</tbody></table>';
        usersListWrap.querySelectorAll('.user-edit-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            openUserEditForm(btn.getAttribute('data-user-id'), btn.getAttribute('data-username'), btn.getAttribute('data-role'));
          });
        });
        usersListWrap.querySelectorAll('.user-reset-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            resetUserPassword(btn.getAttribute('data-user-id'), btn.getAttribute('data-username'));
          });
        });
        usersListWrap.querySelectorAll('.user-domains-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            openUserDomainsForm(btn.getAttribute('data-user-id'), btn.getAttribute('data-username'), btn.getAttribute('data-domain-ids'));
          });
        });
        usersListWrap.querySelectorAll('.user-delete-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            deleteUser(btn.getAttribute('data-user-id'), btn.getAttribute('data-username'));
          });
        });
      })
      .catch(function () { usersListWrap.innerHTML = '<p class="error">Error loading users.</p>'; });
  }

  function openUserEditForm(userId, username, role) {
    hideUserForms();
    var form = document.getElementById('user-edit-form');
    var inner = document.getElementById('user-edit-form-inner');
    var errEl = document.getElementById('user-edit-error');
    if (!form || !inner) return;
    inner.user_id.value = userId;
    inner.username.value = username;
    inner.role.value = role;
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    form.classList.remove('hidden');
  }

  function openUserDomainsForm(userId, username, currentDomainIds) {
    hideUserForms();
    var form = document.getElementById('user-domains-form');
    var inner = document.getElementById('user-domains-form-inner');
    var title = document.getElementById('user-domains-title');
    var fieldset = document.getElementById('user-domains-fieldset');
    var errEl = document.getElementById('user-domains-error');
    if (!form || !inner || !fieldset) return;
    inner.user_id.value = userId;
    if (title) title.textContent = 'Domains for ' + username;
    if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
    var currentIds = currentDomainIds ? currentDomainIds.split(',').filter(Boolean) : [];
    fetchDomains()
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var domains = data.domains || [];
        if (!domains.length) {
          fieldset.innerHTML = '<em>No domains available.</em>';
        } else {
          fieldset.innerHTML = domains.map(function (d) {
            var checked = currentIds.indexOf(d.id) >= 0 ? ' checked' : '';
            return '<label><input type="checkbox" name="domain_id" value="' + escapeHtml(d.id) + '"' + checked + '> ' + escapeHtml(d.name) + '</label>';
          }).join('');
        }
        form.classList.remove('hidden');
      });
  }

  function resetUserPassword(userId, username) {
    if (!confirm('Reset password for ' + username + '? This will generate a new random password.')) return;
    fetch('/api/v1/users/' + encodeURIComponent(userId) + '/reset-password', {
      method: 'POST',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 403) {
          alert('Forbidden: You cannot reset this user\'s password.');
          return null;
        }
        if (r.status === 404) {
          alert('User not found.');
          return null;
        }
        if (!r.ok) {
          alert('Failed to reset password.');
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        alert('New password for ' + username + ':\n\n' + data.password + '\n\nCopy it now — it will not be shown again.');
      })
      .catch(function () { alert('Error resetting password.'); });
  }

  function deleteUser(userId, username) {
    if (!confirm('Delete user "' + username + '"? This cannot be undone. If the user owns any dashboards, ownership will be transferred.')) return;
    fetch('/api/v1/users/' + encodeURIComponent(userId), {
      method: 'DELETE',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.status === 204) {
          loadUsersPage();
          return null;
        }
        if (r.status === 403) {
          alert('Forbidden: You cannot delete this user.');
          return null;
        }
        if (r.status === 404) {
          alert('User not found.');
          return null;
        }
        if (r.status === 400) {
          alert('Cannot delete yourself.');
          return null;
        }
        if (r.status === 409) {
          return r.json().then(function (d) {
            alert(d.detail || 'Cannot delete user: no eligible owner for their dashboards.');
          });
        }
        alert('Failed to delete user.');
        return null;
      })
      .catch(function () { alert('Error deleting user.'); });
  }

  var currentAuditPage = 1;
  var currentAuditPageSize = 50;

  function getAuditStateFromHash() {
    var hash = window.location.hash;
    if (!hash || hash.indexOf('#audit') !== 0) return null;
    var qmark = hash.indexOf('?');
    if (qmark < 0) return { action_type: '', from: '', to: '', actor: '', page: 1 };
    var params = new URLSearchParams(hash.substring(qmark + 1));
    return {
      action_type: params.get('action_type') || '',
      from: params.get('from') || '',
      to: params.get('to') || '',
      actor: params.get('actor') || '',
      page: parseInt(params.get('page'), 10) || 1
    };
  }

  function setAuditStateInHash(state) {
    var params = new URLSearchParams();
    if (state.action_type) params.set('action_type', state.action_type);
    if (state.from) params.set('from', state.from);
    if (state.to) params.set('to', state.to);
    if (state.actor) params.set('actor', state.actor);
    if (state.page && state.page > 1) params.set('page', state.page.toString());
    var qs = params.toString();
    window.location.hash = qs ? 'audit?' + qs : 'audit';
  }

  function buildAuditQueryParams() {
    var actionType = document.getElementById('audit-action-type').value || '';
    var fromVal = document.getElementById('audit-from').value || '';
    var toVal = document.getElementById('audit-to').value || '';
    var actor = document.getElementById('audit-actor').value || '';
    var params = new URLSearchParams();
    params.set('limit', currentAuditPageSize.toString());
    params.set('offset', ((currentAuditPage - 1) * currentAuditPageSize).toString());
    if (actionType) params.set('action_type', actionType);
    if (fromVal) params.set('from', fromVal);
    if (toVal) params.set('to', toVal);
    if (actor) params.set('actor', actor);
    return params.toString();
  }

  function doAuditFilter() {
    var actionType = document.getElementById('audit-action-type').value || '';
    var fromVal = document.getElementById('audit-from').value || '';
    var toVal = document.getElementById('audit-to').value || '';
    var actor = document.getElementById('audit-actor').value || '';
    setAuditStateInHash({ action_type: actionType, from: fromVal, to: toVal, actor: actor, page: currentAuditPage });

    if (!auditEventsWrap) return;
    auditEventsWrap.innerHTML = '<p>Loading…</p>';
    var auditPagination = document.getElementById('audit-pagination');
    if (auditPagination) auditPagination.innerHTML = '';

    fetch('/api/v1/audit?' + buildAuditQueryParams(), { credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 403) {
          auditEventsWrap.innerHTML = '<p class="error">You do not have permission to view the audit log.</p>';
          return null;
        }
        if (!r.ok) {
          auditEventsWrap.innerHTML = '<p class="error">Failed to load audit log.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        var events = data.events || [];
        if (!events.length) {
          auditEventsWrap.innerHTML = '<p><em>No audit events match the filters.</em></p>';
          return;
        }
        auditEventsWrap.innerHTML = '<table><thead><tr><th>Time</th><th>Action</th><th>Outcome</th><th>Summary</th><th>Actor</th></tr></thead><tbody>' +
          events.map(function (e) {
            return '<tr><td>' + escapeHtml(e.timestamp || '') + '</td><td>' + escapeHtml(e.action_type || '') + '</td><td>' + escapeHtml(e.outcome || '') + '</td><td>' + escapeHtml(e.summary || '') + '</td><td>' + escapeHtml(e.actor_user_id || '') + '</td></tr>';
          }).join('') + '</tbody></table>';
        renderAuditPagination(events.length);
      })
      .catch(function () { auditEventsWrap.innerHTML = '<p class="error">Error loading audit log.</p>'; });
  }

  function renderAuditPagination(count) {
    var auditPagination = document.getElementById('audit-pagination');
    if (!auditPagination) return;
    var hasMore = count >= currentAuditPageSize;
    if (currentAuditPage === 1 && !hasMore) {
      auditPagination.innerHTML = '';
      return;
    }
    var html = '<p>Page ' + currentAuditPage + ' ';
    if (currentAuditPage > 1) html += '<a href="#" id="audit-prev-page">← Prev</a> ';
    if (hasMore) html += '<a href="#" id="audit-next-page">Next →</a>';
    html += '</p>';
    auditPagination.innerHTML = html;
    var prevLink = document.getElementById('audit-prev-page');
    var nextLink = document.getElementById('audit-next-page');
    if (prevLink) {
      prevLink.addEventListener('click', function (e) {
        e.preventDefault();
        currentAuditPage = Math.max(1, currentAuditPage - 1);
        doAuditFilter();
      });
    }
    if (nextLink) {
      nextLink.addEventListener('click', function (e) {
        e.preventDefault();
        currentAuditPage = currentAuditPage + 1;
        doAuditFilter();
      });
    }
  }

  function loadAuditPage(runFromHash) {
    if (!auditEventsWrap) return;
    var hashState = runFromHash ? getAuditStateFromHash() : null;
    if (hashState) {
      document.getElementById('audit-action-type').value = hashState.action_type || '';
      document.getElementById('audit-from').value = hashState.from || '';
      document.getElementById('audit-to').value = hashState.to || '';
      document.getElementById('audit-actor').value = hashState.actor || '';
      currentAuditPage = hashState.page || 1;
    } else {
      currentAuditPage = 1;
    }
    doAuditFilter();
  }

  function fetchIngestJobs() {
    return fetch('/api/v1/ingest-jobs', { credentials: 'same-origin' });
  }

  function loadIngestJobsPage() {
    if (!ingestJobsList) return;
    ingestJobsList.innerHTML = '<li><em>Loading…</em></li>';
    fetchIngestJobs()
      .then(function (r) {
        if (!r.ok) { ingestJobsList.innerHTML = '<li class="error">Failed to load jobs</li>'; return []; }
        return r.json();
      })
      .then(function (data) {
        const jobs = (data && data.jobs) ? data.jobs : [];
        ingestJobsList.innerHTML = jobs.length
          ? jobs.map(function (j) {
              return '<li><a href="#" data-job-id="' + escapeHtml(j.job_id) + '">' + escapeHtml(j.job_id) + '</a> — ' + escapeHtml(j.state) + ' — ' + escapeHtml(j.submitted_at || '') + '</li>';
            }).join('')
          : '<li><em>No ingest jobs</em></li>';
        ingestJobsList.querySelectorAll('a[data-job-id]').forEach(function (a) {
          a.addEventListener('click', function (e) {
            e.preventDefault();
            loadIngestJobDetail(a.getAttribute('data-job-id'));
          });
        });
      })
      .catch(function () { ingestJobsList.innerHTML = '<li class="error">Error loading jobs</li>'; });
  }

  function loadIngestJobDetail(jobId) {
    if (!ingestJobDetailTitle || !ingestJobDetailContent) return;
    showIngestJobDetail();
    ingestJobDetailTitle.textContent = 'Job ' + escapeHtml(jobId);
    ingestJobDetailContent.innerHTML = '<p>Loading…</p>';
    fetch('/api/v1/ingest-jobs/' + encodeURIComponent(jobId), { credentials: 'same-origin' })
      .then(function (r) {
        if (r.status === 404) {
          ingestJobDetailContent.innerHTML = '<p class="error">Job not found.</p>';
          return null;
        }
        if (!r.ok) {
          ingestJobDetailContent.innerHTML = '<p class="error">Failed to load job.</p>';
          return null;
        }
        return r.json();
      })
      .then(function (job) {
        if (!job) return;
        var html = '<p><strong>State:</strong> ' + escapeHtml(job.state) + ' · <strong>Submitted:</strong> ' + escapeHtml(job.submitted_at || '') + '</p>';
        html += '<p>Accepted: ' + (job.accepted_count || 0) + ', Duplicate: ' + (job.duplicate_count || 0) + ', Invalid: ' + (job.invalid_count || 0) + ', Rejected: ' + (job.rejected_count || 0) + '</p>';
        var items = job.items || [];
        if (items.length) {
          html += '<table><thead><tr><th>Item</th><th>Report type</th><th>Domain</th><th>Status</th><th>Reason</th></tr></thead><tbody>';
          items.forEach(function (i) {
            html += '<tr><td>' + escapeHtml(i.item_id || '') + '</td><td>' + escapeHtml(i.report_type_detected || '') + '</td><td>' + escapeHtml(i.domain_detected || '') + '</td><td>' + escapeHtml(i.status || '') + '</td><td>' + escapeHtml(i.status_reason || '') + '</td></tr>';
          });
          html += '</tbody></table>';
        }
        ingestJobDetailContent.innerHTML = html;
      })
      .catch(function () { ingestJobDetailContent.innerHTML = '<p class="error">Error loading job.</p>'; });
  }

  function checkAuth() {
    fetchMe()
      .then(function (r) {
        if (r.status === 401) {
          showLogin();
          return;
        }
        return r.json().then(function (data) {
          showDomains();
          loadDomainsPage(data);
        });
      })
      .catch(function () { showLogin(); });
  }

  loginForm.addEventListener('submit', function (e) {
    e.preventDefault();
    setLoginError('');
    const form = e.target;
    const body = JSON.stringify({
      username: form.username.value.trim(),
      password: form.password.value
    });
    fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: body,
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          showDomains();
          return fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          setLoginError(d.detail || 'Login failed');
        });
      })
      .catch(function () { setLoginError('Login failed'); });
  });

  domainForm.addEventListener('submit', function (e) {
    e.preventDefault();
    setDomainError('');
    const name = (e.target.name.value || '').trim();
    if (!name) {
      setDomainError('Name required');
      return;
    }
    fetch('/api/v1/domains', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ name: name }),
      credentials: 'same-origin'
    })
      .then(function (r) {
        if (r.ok) {
          e.target.name.value = '';
          return fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
        }
        return r.json().catch(function () { return {}; }).then(function (d) {
          setDomainError(d.detail || 'Failed to add domain');
        });
      })
      .catch(function () { setDomainError('Failed to add domain'); });
  });

  if (document.getElementById('archive-domain-form-inner')) {
    document.getElementById('archive-domain-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var domainId = document.getElementById('archive-domain-id').value;
      var retentionDays = document.getElementById('archive-retention-days').value;
      doArchiveDomain(domainId, retentionDays);
    });
  }
  if (document.getElementById('archive-domain-cancel')) {
    document.getElementById('archive-domain-cancel').addEventListener('click', function () {
      hideArchiveForm();
    });
  }
  if (document.getElementById('set-retention-form-inner')) {
    document.getElementById('set-retention-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var domainId = document.getElementById('set-retention-domain-id').value;
      var retentionDays = document.getElementById('set-retention-days').value;
      doSetRetention(domainId, retentionDays);
    });
  }
  if (document.getElementById('set-retention-cancel')) {
    document.getElementById('set-retention-cancel').addEventListener('click', function () {
      hideSetRetentionForm();
    });
  }

  logoutLink.addEventListener('click', function (e) {
    e.preventDefault();
    fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' })
      .then(function () { showLogin(); });
  });

  if (document.getElementById('link-dashboards')) {
    document.getElementById('link-dashboards').addEventListener('click', function (e) {
      e.preventDefault();
      showDashboards();
      loadDashboardsPage();
    });
  }
  if (document.getElementById('link-ingest-jobs')) {
    document.getElementById('link-ingest-jobs').addEventListener('click', function (e) {
      e.preventDefault();
      showIngestJobs();
      loadIngestJobsPage();
    });
  }
  if (document.getElementById('link-ingest-jobs-from-dash')) {
    document.getElementById('link-ingest-jobs-from-dash').addEventListener('click', function (e) {
      e.preventDefault();
      showIngestJobs();
      loadIngestJobsPage();
    });
  }
  if (document.getElementById('link-domains-from-ingest')) {
    document.getElementById('link-domains-from-ingest').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('link-dashboards-from-ingest')) {
    document.getElementById('link-dashboards-from-ingest').addEventListener('click', function (e) {
      e.preventDefault();
      showDashboards();
      loadDashboardsPage();
    });
  }
  if (document.getElementById('link-ingest-jobs-back')) {
    document.getElementById('link-ingest-jobs-back').addEventListener('click', function (e) {
      e.preventDefault();
      showIngestJobs();
      loadIngestJobsPage();
    });
  }
  if (document.getElementById('ingest-job-view-btn')) {
    document.getElementById('ingest-job-view-btn').addEventListener('click', function () {
      var input = document.getElementById('ingest-job-id-input');
      var id = input && input.value ? input.value.trim() : '';
      if (id) loadIngestJobDetail(id);
    });
  }
  if (document.getElementById('logout-link-ingest')) {
    document.getElementById('logout-link-ingest').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('logout-link-ingest-detail')) {
    document.getElementById('logout-link-ingest-detail').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('link-domains')) {
    document.getElementById('link-domains').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('link-audit-back')) {
    document.getElementById('link-audit-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('logout-link-audit')) {
    document.getElementById('logout-link-audit').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('link-dashboards-back')) {
    document.getElementById('link-dashboards-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDashboards();
      loadDashboardsPage();
    });
  }
  if (document.getElementById('link-export-dashboard')) {
    document.getElementById('link-export-dashboard').addEventListener('click', function (e) {
      e.preventDefault();
      doExportDashboard();
    });
  }
  if (document.getElementById('logout-link2')) {
    document.getElementById('logout-link2').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('logout-link3')) {
    document.getElementById('logout-link3').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }

  if (document.getElementById('link-import-dashboard')) {
    document.getElementById('link-import-dashboard').addEventListener('click', function (e) {
      e.preventDefault();
      var form = document.getElementById('import-dashboard-form');
      if (form) {
        form.classList.remove('hidden');
        updateImportForm();
      }
    });
  }
  if (document.getElementById('import-dashboard-toggle-close')) {
    document.getElementById('import-dashboard-toggle-close').addEventListener('click', function (e) {
      e.preventDefault();
      var form = document.getElementById('import-dashboard-form');
      if (form) form.classList.add('hidden');
    });
  }
  if (document.getElementById('import-yaml-textarea')) {
    document.getElementById('import-yaml-textarea').addEventListener('input', updateImportForm);
    document.getElementById('import-yaml-textarea').addEventListener('change', updateImportForm);
  }
  if (document.getElementById('import-dashboard-submit')) {
    document.getElementById('import-dashboard-submit').addEventListener('click', doImportDashboard);
  }
  if (dashboardForm) {
    dashboardForm.addEventListener('submit', function (e) {
      e.preventDefault();
      setDashboardFormError('');
      const name = (e.target.name.value || '').trim();
      const domainIds = Array.from(dashboardDomainsFieldset.querySelectorAll('input[name=domain_id]:checked')).map(function (c) { return c.value; });
      if (!name) { setDashboardFormError('Name required'); return; }
      if (!domainIds.length) { setDashboardFormError('Select at least one domain'); return; }
      fetch('/api/v1/dashboards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ name: name, description: (e.target.description && e.target.description.value) || '', domain_ids: domainIds }),
        credentials: 'same-origin'
      })
        .then(function (r) {
          if (r.ok) {
            e.target.name.value = '';
            if (e.target.description) e.target.description.value = '';
            dashboardDomainsFieldset.querySelectorAll('input:checked').forEach(function (c) { c.checked = false; });
            loadDashboardsPage();
            return;
          }
          return r.json().catch(function () { return {}; }).then(function (d) { setDashboardFormError(d.detail || 'Failed to create dashboard'); });
        })
        .catch(function () { setDashboardFormError('Failed to create dashboard'); });
    });
  }

  if (auditLinkWrap) {
    auditLinkWrap.addEventListener('click', function (e) {
      if (e.target && e.target.id === 'link-audit') {
        e.preventDefault();
        showAudit();
        loadAuditPage(false);
      }
    });
  }
  if (document.getElementById('audit-filter-form')) {
    document.getElementById('audit-filter-form').addEventListener('submit', function (e) {
      e.preventDefault();
      currentAuditPage = 1;
      doAuditFilter();
    });
  }
  if (apikeysLinkWrap) {
    apikeysLinkWrap.addEventListener('click', function (e) {
      if (e.target && e.target.id === 'link-apikeys') {
        e.preventDefault();
        showApikeys();
        loadApikeysPage();
      }
    });
  }
  if (document.getElementById('link-apikeys-back')) {
    document.getElementById('link-apikeys-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('logout-link-apikeys')) {
    document.getElementById('logout-link-apikeys').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('apikey-form')) {
    document.getElementById('apikey-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target;
      var errEl = document.getElementById('apikey-form-error');
      var msgEl = document.getElementById('apikey-created-msg');
      if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
      if (msgEl) msgEl.classList.add('hidden');
      var nickname = (form.nickname && form.nickname.value) ? form.nickname.value.trim() : '';
      var description = (form.description && form.description.value) ? form.description.value : '';
      var domainIds = Array.from(document.querySelectorAll('#apikey-domains-fieldset input[name=domain_id]:checked')).map(function (c) { return c.value; });
      var scopes = Array.from(document.querySelectorAll('#apikey-scopes-fieldset input[name=scope]:checked')).map(function (c) { return c.value; });
      if (!nickname) { if (errEl) { errEl.textContent = 'Nickname required'; errEl.classList.remove('hidden'); } return; }
      if (!domainIds.length) { if (errEl) { errEl.textContent = 'Select at least one domain'; errEl.classList.remove('hidden'); } return; }
      if (!scopes.length) { if (errEl) { errEl.textContent = 'Select at least one scope'; errEl.classList.remove('hidden'); } return; }
      fetch('/api/v1/apikeys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ nickname: nickname, description: description, domain_ids: domainIds, scopes: scopes }),
        credentials: 'same-origin'
      })
        .then(function (r) {
          if (r.ok) {
            return r.json().then(function (data) {
              var newKey = data.key || '';
              form.nickname.value = '';
              if (form.description) form.description.value = '';
              document.querySelectorAll('#apikey-domains-fieldset input:checked').forEach(function (c) { c.checked = false; });
              document.querySelectorAll('#apikey-scopes-fieldset input:checked').forEach(function (c) { c.checked = false; });
              loadApikeysPage(true);
              if (msgEl) {
                msgEl.textContent = 'Created. Copy the key now — it will not be shown again: ' + newKey;
                msgEl.classList.remove('hidden');
              }
            });
          }
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (errEl) { errEl.textContent = d.detail || 'Failed to create key'; errEl.classList.remove('hidden'); }
          });
        })
        .catch(function () { if (errEl) { errEl.textContent = 'Failed to create key'; errEl.classList.remove('hidden'); } });
    });
  }

  if (usersLinkWrap) {
    usersLinkWrap.addEventListener('click', function (e) {
      if (e.target && e.target.id === 'link-users') {
        e.preventDefault();
        showUsers();
        loadUsersPage();
      }
    });
  }
  if (document.getElementById('link-users-back')) {
    document.getElementById('link-users-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('logout-link-users')) {
    document.getElementById('logout-link-users').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (document.getElementById('user-form')) {
    document.getElementById('user-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target;
      var errEl = document.getElementById('user-form-error');
      var msgEl = document.getElementById('user-created-msg');
      if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
      if (msgEl) msgEl.classList.add('hidden');
      var username = (form.username && form.username.value) ? form.username.value.trim() : '';
      var role = (form.role && form.role.value) ? form.role.value : '';
      if (!username) { if (errEl) { errEl.textContent = 'Username required'; errEl.classList.remove('hidden'); } return; }
      if (!role) { if (errEl) { errEl.textContent = 'Role required'; errEl.classList.remove('hidden'); } return; }
      fetch('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ username: username, role: role }),
        credentials: 'same-origin'
      })
        .then(function (r) {
          if (r.status === 201) {
            return r.json().then(function (data) {
              form.username.value = '';
              form.role.value = 'viewer';
              loadUsersPage(true);
              if (msgEl) {
                msgEl.textContent = 'Created. Password: ' + (data.password || '') + ' — Copy it now, it will not be shown again.';
                msgEl.classList.remove('hidden');
              }
            });
          }
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (errEl) { errEl.textContent = d.detail || 'Failed to create user'; errEl.classList.remove('hidden'); }
          });
        })
        .catch(function () { if (errEl) { errEl.textContent = 'Failed to create user'; errEl.classList.remove('hidden'); } });
    });
  }
  if (document.getElementById('user-edit-form-inner')) {
    document.getElementById('user-edit-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target;
      var errEl = document.getElementById('user-edit-error');
      if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
      var userId = form.user_id.value;
      var username = (form.username && form.username.value) ? form.username.value.trim() : '';
      var role = (form.role && form.role.value) ? form.role.value : '';
      if (!username) { if (errEl) { errEl.textContent = 'Username required'; errEl.classList.remove('hidden'); } return; }
      fetch('/api/v1/users/' + encodeURIComponent(userId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ username: username, role: role }),
        credentials: 'same-origin'
      })
        .then(function (r) {
          if (r.ok) {
            hideUserForms();
            loadUsersPage();
            return;
          }
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (errEl) { errEl.textContent = d.detail || 'Failed to update user'; errEl.classList.remove('hidden'); }
          });
        })
        .catch(function () { if (errEl) { errEl.textContent = 'Failed to update user'; errEl.classList.remove('hidden'); } });
    });
  }
  if (document.getElementById('user-edit-cancel')) {
    document.getElementById('user-edit-cancel').addEventListener('click', function () {
      hideUserForms();
    });
  }
  if (document.getElementById('user-domains-form-inner')) {
    document.getElementById('user-domains-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target;
      var errEl = document.getElementById('user-domains-error');
      if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
      var userId = form.user_id.value;
      var fieldset = document.getElementById('user-domains-fieldset');
      var selectedIds = Array.from(fieldset.querySelectorAll('input[name=domain_id]:checked')).map(function (c) { return c.value; });
      var allIds = Array.from(fieldset.querySelectorAll('input[name=domain_id]')).map(function (c) { return c.value; });
      var currentChecked = Array.from(fieldset.querySelectorAll('input[name=domain_id]')).filter(function (c) { return c.checked; }).map(function (c) { return c.value; });
      fetch('/api/v1/users/' + encodeURIComponent(userId), { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var currentDomainIds = (data.user && data.user.domain_ids) ? data.user.domain_ids : [];
          var toAdd = selectedIds.filter(function (id) { return currentDomainIds.indexOf(id) < 0; });
          var toRemove = currentDomainIds.filter(function (id) { return selectedIds.indexOf(id) < 0 && allIds.indexOf(id) >= 0; });
          var promises = [];
          if (toAdd.length) {
            promises.push(fetch('/api/v1/users/' + encodeURIComponent(userId) + '/domains', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
              body: JSON.stringify({ domain_ids: toAdd }),
              credentials: 'same-origin'
            }));
          }
          toRemove.forEach(function (domainId) {
            promises.push(fetch('/api/v1/users/' + encodeURIComponent(userId) + '/domains/' + encodeURIComponent(domainId), {
              method: 'DELETE',
              headers: { 'X-CSRF-Token': getCsrfToken() },
              credentials: 'same-origin'
            }));
          });
          return Promise.all(promises);
        })
        .then(function (responses) {
          var failed = responses.filter(function (r) { return r.status === 403; });
          if (failed.length) {
            if (errEl) { errEl.textContent = 'Forbidden: Cannot assign/remove some domains.'; errEl.classList.remove('hidden'); }
            return;
          }
          hideUserForms();
          loadUsersPage();
        })
        .catch(function () { if (errEl) { errEl.textContent = 'Failed to update domains'; errEl.classList.remove('hidden'); } });
    });
  }
  if (document.getElementById('user-domains-cancel')) {
    document.getElementById('user-domains-cancel').addEventListener('click', function () {
      hideUserForms();
    });
  }

  if (document.getElementById('dashboard-edit-form-inner')) {
    document.getElementById('dashboard-edit-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var form = e.target;
      var errEl = document.getElementById('dashboard-edit-error');
      if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }
      var dashboardId = form.dashboard_id.value;
      var name = (form.name && form.name.value) ? form.name.value.trim() : '';
      var description = (form.description && form.description.value) ? form.description.value : '';
      var fieldset = document.getElementById('dashboard-edit-domains-fieldset');
      var domainIds = Array.from(fieldset.querySelectorAll('input[name=domain_id]:checked')).map(function (c) { return c.value; });
      if (!name) { if (errEl) { errEl.textContent = 'Name required'; errEl.classList.remove('hidden'); } return; }
      if (!domainIds.length) { if (errEl) { errEl.textContent = 'Select at least one domain'; errEl.classList.remove('hidden'); } return; }
      fetch('/api/v1/dashboards/' + encodeURIComponent(dashboardId), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
        body: JSON.stringify({ name: name, description: description, domain_ids: domainIds }),
        credentials: 'same-origin'
      })
        .then(function (r) {
          if (r.ok) {
            hideDashboardEditForm();
            loadDashboardDetail(dashboardId);
            return;
          }
          return r.json().catch(function () { return {}; }).then(function (d) {
            if (errEl) { errEl.textContent = d.detail || 'Failed to update dashboard'; errEl.classList.remove('hidden'); }
          });
        })
        .catch(function () { if (errEl) { errEl.textContent = 'Failed to update dashboard'; errEl.classList.remove('hidden'); } });
    });
  }
  if (document.getElementById('dashboard-edit-cancel')) {
    document.getElementById('dashboard-edit-cancel').addEventListener('click', function () {
      hideDashboardEditForm();
    });
  }

  if (document.getElementById('dashboard-share-form-inner')) {
    document.getElementById('dashboard-share-form-inner').addEventListener('submit', function (e) {
      e.preventDefault();
      var userId = document.getElementById('share-user-select').value;
      var accessLevel = document.getElementById('share-access-select').value;
      if (!userId) {
        var errEl = document.getElementById('dashboard-share-error');
        if (errEl) { errEl.textContent = 'Select a user'; errEl.classList.remove('hidden'); }
        return;
      }
      doShareDashboard(userId, accessLevel);
    });
  }

  if (document.getElementById('link-search')) {
    document.getElementById('link-search').addEventListener('click', function (e) {
      e.preventDefault();
      showSearch();
      loadSearchPage(false);
    });
  }
  if (document.getElementById('link-search-back')) {
    document.getElementById('link-search-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('logout-link-search')) {
    document.getElementById('logout-link-search').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (reportDetailClose) {
    reportDetailClose.addEventListener('click', function (e) {
      e.preventDefault();
      hideReportDetailModal();
    });
  }
  if (searchForm) {
    searchForm.addEventListener('submit', function (e) {
      e.preventDefault();
      currentSearchPage = 1;
      doSearch();
    });
  }

  var dashboardFilterForm = document.getElementById('dashboard-filter-form');
  if (dashboardFilterForm) {
    dashboardFilterForm.addEventListener('submit', function (e) {
      e.preventDefault();
      currentDashboardPage = 1;
      doDashboardFilter();
    });
  }

  if (document.getElementById('link-upload')) {
    document.getElementById('link-upload').addEventListener('click', function (e) {
      e.preventDefault();
      showUpload();
      loadUploadPage();
    });
  }
  if (document.getElementById('link-upload-back')) {
    document.getElementById('link-upload-back').addEventListener('click', function (e) {
      e.preventDefault();
      showDomains();
      fetchMe().then(function (m) { return m.json(); }).then(loadDomainsPage);
    });
  }
  if (document.getElementById('logout-link-upload')) {
    document.getElementById('logout-link-upload').addEventListener('click', function (e) {
      e.preventDefault();
      fetch('/api/v1/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': getCsrfToken() }, credentials: 'same-origin' }).then(function () { showLogin(); });
    });
  }
  if (uploadForm) {
    uploadForm.addEventListener('submit', function (e) {
      e.preventDefault();
      submitUpload();
    });
  }

  window.addEventListener('hashchange', function () {
    var hash = window.location.hash;
    if (hash && hash.indexOf('#search') === 0) {
      showSearch();
      loadSearchPage(true);
    } else if (hash && hash.indexOf('#audit') === 0) {
      showAudit();
      loadAuditPage(true);
    } else if (hash && hash.indexOf('#dashboard/') === 0) {
      var state = getDashboardStateFromHash();
      if (state && state.dashboard_id) {
        loadDashboardDetail(state.dashboard_id, state);
      }
    }
  });

  checkAuth();
})();
