// TravelVerse Universal Dynamic API Resolver
(function() {
  function getApiBase() {
    if (typeof window !== 'undefined' && window.TRAVELVERSE_API_BASE) {
      return window.TRAVELVERSE_API_BASE;
    }
    if (typeof window !== 'undefined' && window.location && window.location.protocol && window.location.protocol.startsWith('http')) {
      const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (!isLocal || window.location.port === '8000') {
        return window.location.origin;
      }
      return `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return 'http://127.0.0.1:8000';
  }

  const apiBase = getApiBase();
  window.API_BASE = apiBase;
  window.apiBase = apiBase;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { API_BASE: apiBase };
  }
})();
