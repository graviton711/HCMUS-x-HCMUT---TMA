import { Component, type ReactNode } from 'react';

export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    const english = document.documentElement.lang === 'en';
    return (
      <main className="empty-state" role="alert">
        <h1>{english ? 'This page could not be displayed.' : 'Chưa thể hiển thị trang này.'}</h1>
        <p>
          {english
            ? 'Your saved drafts are kept in this browser.'
            : 'Bản nháp đã lưu vẫn được giữ trên trình duyệt.'}
        </p>
        <button className="btn" onClick={() => window.location.reload()}>
          {english ? 'Reload page' : 'Tải lại trang'}
        </button>
      </main>
    );
  }
}
