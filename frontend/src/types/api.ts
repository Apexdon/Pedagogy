// Generic API response types
export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
}

// HTTP Error response
export interface HttpErrorResponse {
  detail: string;
}

// Generic success response
export interface SuccessResponse {
  success: boolean;
  message: string;
}
