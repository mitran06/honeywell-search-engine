// src/components/panels/CenterPanelViewer.tsx
import React from 'react';
import ViewerPage from '@/pages/ViewerPage'; 

export function CenterPanelViewer() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <ViewerPage />
    </div>
  );
}

export default CenterPanelViewer;
