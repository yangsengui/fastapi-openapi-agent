export type LoaderConfig = {
  baseUrl?: string;
  title?: string;
  description?: string;
  container?: string | HTMLElement;
  theme?: "default" | "ocean";
  open?: boolean;
  width?: number;
  minWidth?: number;
  maxWidth?: number;
  request?: (input: LoaderRequestInput) => Response | Promise<Response>;
};

export type LoaderRequestInput = {
  url: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string | null;
  stream?: boolean;
};
