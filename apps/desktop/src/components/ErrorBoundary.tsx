/**
 * Names a crash instead of letting it empty the window (spec §67: never hide failures).
 *
 * When a render throws and nothing catches it, React unmounts the entire tree. The window
 * goes white, no message is shown, and the only record is a console the user cannot open in
 * a packaged build — so a crash is indistinguishable from the app doing nothing at all.
 * That happened for real: clicking Retry on the "cannot reach the local AI service" card
 * replaced the card with an empty window.
 *
 * ServiceGate explains the failures it knows how to anticipate. This is the backstop for the
 * ones it does not, and it sits above the router so a crash on any page still renders.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Alert, Button } from "./ui";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled render error", error, info.componentStack);
  }

  private readonly dismiss = (): void => {
    this.setState({ error: null });
  };

  private readonly reload = (): void => {
    window.location.reload();
  };

  override render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex h-full items-center justify-center p-8">
        <Alert tone="danger" title="Something in the app stopped working">
          <p>{error.message || "The interface hit an error it could not recover from."}</p>
          {error.stack !== undefined && (
            <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-bg p-3 font-mono text-xs whitespace-pre-wrap">
              {error.stack}
            </pre>
          )}
          <div className="mt-3 flex gap-2">
            <Button onClick={this.dismiss}>Try again</Button>
            <Button variant="secondary" onClick={this.reload}>
              Reload
            </Button>
          </div>
        </Alert>
      </div>
    );
  }
}
