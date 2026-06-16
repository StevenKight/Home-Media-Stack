import { client } from '../api/client.gen';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

client.setConfig({ baseUrl: BASE_URL });

// Attach the stored JWT to every request automatically.
// After login, call: localStorage.setItem('access_token', token)
// To log out, call:  localStorage.removeItem('access_token')
client.interceptors.request.use((request) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    request.headers.set('Authorization', `Bearer ${token}`);
  }
  return request;
});

export { client };
