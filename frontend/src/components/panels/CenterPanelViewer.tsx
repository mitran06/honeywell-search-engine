// src/components/panels/CenterPanelViewer.tsx
import React from 'react';
import ViewerPage from '@/pages/ViewerPage'; // existing viewer is page but we can reuse
// ViewerPage currently renders Header itself; we'll create a small wrapper that uses the viewer logic only.
// If ViewerPage includes Header, we will instead import internal viewer logic. For now assume ViewerPage exports default viewer component without header (if it uses Header, we'll adapt in next steps).

export function CenterPanelViewer() {
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <ViewerPage />
    </div>
  );
}

export default CenterPanelViewer;
