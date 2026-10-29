import axios from 'axios';

const investigationClient = axios.create({ baseURL: '/api/v1/investigation', timeout: 30000 });
const graphClient = axios.create({ baseURL: 'http://localhost:8001/api/v1/graph', timeout: 15000 });

export const investigationApi = {
  health: () => axios.get('/health'),
  analyze: (inputValue, inputType = 'observation_id', limitRelated = 10) =>
    investigationClient.post('/analyze', null, {
      params: { input_value: inputValue, input_type: inputType, limit_related: limitRelated },
    }),
  getInvestigation: (id) => investigationClient.get(`/${encodeURIComponent(id)}`),
  listInvestigations: (limit = 50) => investigationClient.get('', { params: { limit } }),
};

export const archiveApi = {
  listObservations: (options = {}) => investigationClient.get('/archive/observations', {
    params: options,
    timeout: 120000,
  }),
  runExperiment: (experiment) => investigationClient.post('/archive/run', experiment, {
    timeout: 300000,
  }),
};

export const graphApi = {
  health: () => axios.get('http://localhost:8001/health', { timeout: 5000 }),
  observationNeighborhood: (observationId, limit = 150) =>
    graphClient.get(`/observation/${encodeURIComponent(observationId)}`, { params: { limit } }),
};
