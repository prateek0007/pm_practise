import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full bg-background">
          <div className="flex-1 p-6">
            <h1 className="text-2xl font-bold text-red-400 mb-4">Something went wrong</h1>
            <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-4">
              <h2 className="text-lg font-semibold text-red-300 mb-2">Error Details:</h2>
              <pre className="text-sm text-red-200 whitespace-pre-wrap">
                {this.state.error && this.state.error.toString()}
              </pre>
            </div>
            <div className="bg-gray-800 border border-gray-600 rounded-lg p-4">
              <h2 className="text-lg font-semibold text-gray-300 mb-2">Stack Trace:</h2>
              <pre className="text-sm text-gray-400 whitespace-pre-wrap">
                {this.state.errorInfo.componentStack}
              </pre>
            </div>
            <button 
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
