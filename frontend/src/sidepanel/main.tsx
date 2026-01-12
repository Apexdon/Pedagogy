import React from 'react';
import ReactDOM from 'react-dom/client';
import { SidePanelApp } from './SidePanelApp';
import './sidepanel.css';

ReactDOM.createRoot(document.getElementById('panel-root')!).render(
  <React.StrictMode>
    <SidePanelApp />
  </React.StrictMode>
);
