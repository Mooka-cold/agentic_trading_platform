import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, LogIn, UserPlus } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/data/api';

export default function LoginPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (isLogin) {
        const res = await api.post('/api/v1/auth/login/email', { email, password });
        localStorage.setItem('access_token', res.data.access_token);
        toast.success('Login successful');
        navigate('/');
      } else {
        await api.post('/auth/register', { email, password });
        toast.success('Registration successful. Please log in.');
        setIsLogin(true);
      }
    } catch (err: any) {
      toast.error(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-background p-4">
      <div className="w-full max-w-md bg-card border border-border rounded-lg shadow-xl p-8 space-y-6 relative overflow-hidden">
        
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-32 h-32 bg-primary/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

        <div className="flex flex-col items-center gap-3 relative z-10">
          <div className="p-3 bg-secondary rounded-full border border-border">
            <Activity className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-mono font-bold text-primary text-glow">AGENT TRADE</h1>
          <p className="text-sm font-mono text-muted-foreground text-center">
            {isLogin ? 'Sign in to access your multi-agent terminal' : 'Create an account to deploy your swarm'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 relative z-10">
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-secondary/50 border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors"
              placeholder="trader@example.com"
            />
          </div>
          <div>
            <label className="block text-xs font-mono text-muted-foreground mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-secondary/50 border border-border rounded px-3 py-2 text-sm font-mono focus:outline-none focus:border-primary transition-colors"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-primary/10 text-primary border border-primary/50 rounded flex items-center justify-center gap-2 hover:bg-primary/20 transition-all font-mono text-sm mt-6 disabled:opacity-50"
          >
            {loading ? (
              <Activity className="h-4 w-4 animate-spin" />
            ) : isLogin ? (
              <LogIn className="h-4 w-4" />
            ) : (
              <UserPlus className="h-4 w-4" />
            )}
            {isLogin ? 'Initialize Session' : 'Register Terminal'}
          </button>
        </form>

        <div className="text-center relative z-10 mt-4">
          <button
            type="button"
            onClick={() => setIsLogin(!isLogin)}
            className="text-xs font-mono text-muted-foreground hover:text-primary transition-colors"
          >
            {isLogin ? "Need an account? Register" : "Already have an account? Login"}
          </button>
        </div>
      </div>
    </div>
  );
}
