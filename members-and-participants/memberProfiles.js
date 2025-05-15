// exchangeProfiles.js
import { fetchData, clearCache, setRateLimit } from '../fetchUtil.js';

const BASE_URL = 'https://www.idx.co.id/primary';

const DEFAULT_OPTIONS = {};
const DEFAULT_CACHE_OPTIONS = {
  useCache: true,
  ttl: 15 * 60 * 1000 // 15 minutes
};
const DEFAULT_RETRY_OPTIONS = {
  maxRetries: 3,
  baseDelay: 1000
};

// Rate limit configuration
export const configureRateLimit = (maxRequests = 5, timeWindowMs = 1000) => {
  setRateLimit({ maxRequests, timeWindow: timeWindowMs });
};

// Clear all cached responses
export const clearApiCache = () => {
  clearCache();
};

// Exchange Members
export const getBrokerSearch = (options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetBrokerSearch?option=0&license=&start=0&length=9999`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getBrokerDetail = (code, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetBrokerDetail?code=${encodeURIComponent(code)}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getMkbdSummary = (code, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetMkbdSummary?code=${encodeURIComponent(code)}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getBranch = (code, start = 0, length = 10, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetBranch?code=${encodeURIComponent(code)}&start=${start}&length=${length}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

// Participants
export const getParticipantSearch = (options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetParticipantSearch?draw=1&start=0&length=9999&licenseType=All`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getParticipantDetail = (code, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetParticipantDetail?code=${encodeURIComponent(code)}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

// Primary Dealers
export const getPrimaryDealerSearch = (options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetPrimaryDealerSearch?draw=1&start=0&length=9999&licenseType=0`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getPrimaryDealerDetail = (code, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/ExchangeMember/GetPrimaryDealerDetail?code=${encodeURIComponent(code)}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

// SPPA
export const getSPPAProfile = (options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/NewsAnnouncement/GetSPPAProfile?start=0&length=9999`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );

export const getSPPAProfileDetail = (id, options = {}, cacheOptions = {}) =>
  fetchData(
    `${BASE_URL}/NewsAnnouncement/GetSPPAProfileDetail?id=${encodeURIComponent(id)}`,
    { ...DEFAULT_OPTIONS, ...options },
    { ...DEFAULT_CACHE_OPTIONS, ...cacheOptions },
    DEFAULT_RETRY_OPTIONS
  );
