'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertCircle, RefreshCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    // Attempt to recover by reloading the window if component reset isn't enough
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-6 text-center bg-zinc-900/50 rounded-lg border border-zinc-800">
          <AlertCircle className="w-12 h-12 text-rose-500 mb-4" />
          <h2 className="text-lg font-semibold text-zinc-100 mb-2">Something went wrong</h2>
          <p className="text-zinc-400 text-sm max-w-md mb-6">
            We encountered an unexpected error while loading this component. Please try refreshing.
          </p>
          <Button 
            onClick={this.handleReset}
            variant="outline"
            className="flex items-center gap-2"
          >
            <RefreshCcw className="w-4 h-4" />
            Reload Component
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
