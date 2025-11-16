// Performance monitoring hook
import { useEffect, useCallback } from 'react';

interface PerformanceMetrics {
  name: string;
  duration: number;
  timestamp: number;
}

const metrics: PerformanceMetrics[] = [];
const MAX_METRICS = 100;

// Performance utilities
export const performanceUtils = {
  // Measure function execution time
  measure: async <T>(name: string, fn: () => Promise<T>): Promise<T> => {
    const start = performance.now();
    try {
      const result = await fn();
      const duration = performance.now() - start;

      metrics.push({
        name,
        duration,
        timestamp: Date.now(),
      });

      // Keep only last MAX_METRICS
      if (metrics.length > MAX_METRICS) {
        metrics.shift();
      }

      // Log slow operations (>1s)
      if (duration > 1000) {
        console.warn(`Slow operation detected: ${name} took ${duration.toFixed(2)}ms`);
      }

      return result;
    } catch (error) {
      const duration = performance.now() - start;
      console.error(`Operation failed: ${name} after ${duration.toFixed(2)}ms`, error);
      throw error;
    }
  },

  // Get metrics
  getMetrics: () => [...metrics],

  // Get average duration for a specific operation
  getAverage: (name: string): number => {
    const filtered = metrics.filter((m) => m.name === name);
    if (filtered.length === 0) return 0;
    const sum = filtered.reduce((acc, m) => acc + m.duration, 0);
    return sum / filtered.length;
  },

  // Clear all metrics
  clear: () => {
    metrics.length = 0;
  },
};

// Hook for component performance monitoring
export function usePerformance(componentName: string) {
  useEffect(() => {
    const start = performance.now();

    return () => {
      const duration = performance.now() - start;
      if (duration > 500) {
        console.warn(
          `Component ${componentName} was mounted for ${duration.toFixed(2)}ms (slow)`
        );
      }
    };
  }, [componentName]);

  const measureRender = useCallback(
    (operationName: string) => {
      const start = performance.now();
      return () => {
        const duration = performance.now() - start;
        performanceUtils.measure(`${componentName}.${operationName}`, async () => {
          return Promise.resolve(duration);
        });
      };
    },
    [componentName]
  );

  return { measureRender };
}

// Debounce hook for performance
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

// React import
import React from 'react';
