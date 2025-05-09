import { fetchData } from '../fetchUtil.js';

// Base URL for API endpoints
const BASE_URL = 'https://www.idx.co.id/primary';

// API functions
export const getCompanyProfiles = () => {
    return fetchData(`${BASE_URL}/ListedCompany/GetCompanyProfiles?start=0&length=9999`);
};

export const getCompanyProfileDetail = (kodeEmiten) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetCompanyProfilesDetail?KodeEmiten=${kodeEmiten}&language=en-us`);
};

export const getIssuedHistory = (kodeEmiten) => {
    return fetchData(`${BASE_URL}/ListingActivity/GetIssuedHistory?kodeEmiten=${kodeEmiten}&start=0&length=9999`);
};

export const getProfileAnnouncement = (kodeEmiten, dateFrom, dateTo) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetProfileAnnouncement?KodeEmiten=${kodeEmiten}&indexFrom=0&pageSize=10&dateFrom=${dateFrom}&dateTo=${dateTo}&lang=en&keyword=`);
};

export const getCalendar = (kodeEmiten, date) => {
    return fetchData(`${BASE_URL}/Home/GetCalendar?range=${kodeEmiten}&date=${date}`);
};

export const getFinancialReport = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetFinancialReport?periode=audit&year=${year}&indexFrom=0&pageSize=1000&reportType=rdf&kodeEmiten=${kodeEmiten}`);
};

export const getNameChangeHistory = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetPerubahanNamaHistory?KodeEmiten=${kodeEmiten}&Year=${year}`);
};

export const getCoreBusinessHistory = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetCoreBusinessHistory?KodeEmiten=${kodeEmiten}&Year=${year}`);
};

export const getShareholderHistory = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetPemegangSahamHistory?KodeEmiten=${kodeEmiten}&Year=${year}`);
};

export const getControllingShareholderHistory = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetPemegangSahamPengendaliHistory?KodeEmiten=${kodeEmiten}&Year=${year}`);
};

export const getCashDividend = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetDividenTunai?KodeEmiten=${kodeEmiten}&Year=${year}`);
};

export const getStockDividend = (kodeEmiten, year) => {
    return fetchData(`${BASE_URL}/ListedCompany/GetDividenSaham?KodeEmiten=${kodeEmiten}&Year=${year}`);
};
