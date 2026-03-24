import { useState, useEffect } from 'react';
import { useAccount, useSignMessage, useDisconnect } from 'wagmi';
import { API_BASE_URL } from '@/lib/api/base';

const API_URL = API_BASE_URL;

export function useAuth() {
  const { address, isConnected } = useAccount();
  const { signMessageAsync } = useSignMessage();
  const { disconnect } = useDisconnect();
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // Check local storage for token
    const storedToken = localStorage.getItem('auth_token');
    if (storedToken) {
      setToken(storedToken);
    }
  }, []);

  const login = async () => {
    if (!address || !isConnected) return;

    try {
      // 1. Get Nonce
      const nonceRes = await fetch(`${API_URL}/api/v1/auth/nonce?address=${address}`);
      const { nonce } = await nonceRes.json();

      // 2. Sign Message
      const message = `Sign this message to login to AI Trading Dashboard.\n\nNonce: ${nonce}`;
      const signature = await signMessageAsync({ message });

      // 3. Login
      const loginRes = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address, message, signature }),
      });

      if (!loginRes.ok) throw new Error('Login failed');

      const { access_token } = await loginRes.json();
      
      // 4. Save Token
      localStorage.setItem('auth_token', access_token);
      setToken(access_token);
      console.log('Logged in successfully');

    } catch (error) {
      console.error('Login error:', error);
      disconnect();
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    disconnect();
  };

  return { token, login, logout, isConnected, address };
}
