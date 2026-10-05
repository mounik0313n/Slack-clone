export type NetworkState = 'ONLINE' | 'CONNECTING' | 'RECONNECTING' | 'OFFLINE' | 'SYNCING';

export function getConnectionStatus(): NetworkState {
  if (typeof navigator === 'undefined') {
    return 'ONLINE';
  }

  if (!navigator.onLine) {
    return 'OFFLINE';
  }

  return 'ONLINE';
}

export function subscribeToConnectivity(listener: (state: NetworkState) => void): () => void {
  const emit = () => listener(getConnectionStatus());

  window.addEventListener('online', emit);
  window.addEventListener('offline', emit);

  return () => {
    window.removeEventListener('online', emit);
    window.removeEventListener('offline', emit);
  };
}
