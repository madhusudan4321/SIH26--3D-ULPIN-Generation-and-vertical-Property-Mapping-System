/**
 * App — Root Component
 *
 * Provides SelectionContext and renders the Dashboard page.
 */

import { SelectionProvider } from "./hooks/useSelection";
import Dashboard from "./pages/Dashboard";
import "./App.css";

export default function App() {
  return (
    <SelectionProvider>
      <Dashboard />
    </SelectionProvider>
  );
}
