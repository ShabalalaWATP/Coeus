export type HealthResponse = {
  status: "ok" | "ready" | "not_ready";
  service: string;
  environment: string;
  request_id: string;
};

export class ApiClient {
  constructor(private readonly baseUrl: string) {}

  async getJson<TResponse>(path: string, requestId?: string): Promise<TResponse> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: requestId === undefined ? undefined : { "X-Request-ID": requestId },
    });
    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`);
    }
    return (await response.json()) as TResponse;
  }

  async getLiveness(requestId?: string): Promise<HealthResponse> {
    return this.getJson<HealthResponse>("/api/v1/health/live", requestId);
  }
}

export const apiClient = new ApiClient("/api");
