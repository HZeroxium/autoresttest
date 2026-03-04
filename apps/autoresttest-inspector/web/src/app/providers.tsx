import { PropsWithChildren, useState } from "react";
import { CssBaseline, GlobalStyles, ThemeProvider, createTheme } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#12343b",
      contrastText: "#f5f2e9",
    },
    secondary: {
      main: "#d28b36",
      contrastText: "#fffaf2",
    },
    error: {
      main: "#a54730",
    },
    success: {
      main: "#3b7a57",
    },
    background: {
      default: "#f5f2e9",
      paper: "rgba(250, 247, 239, 0.94)",
    },
    text: {
      primary: "#12343b",
      secondary: "#5f6f73",
    },
    divider: "rgba(18, 52, 59, 0.12)",
  },
  shape: {
    borderRadius: 18,
  },
  typography: {
    fontFamily: '"IBM Plex Sans", sans-serif',
    h1: { fontFamily: '"Space Grotesk", sans-serif' },
    h2: { fontFamily: '"Space Grotesk", sans-serif' },
    h3: { fontFamily: '"Space Grotesk", sans-serif' },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
        },
      },
    },
  },
});

export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            staleTime: 1_000,
          },
        },
      }),
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyles
        styles={{
          ":root": {
            colorScheme: "light",
          },
        }}
      />
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}
