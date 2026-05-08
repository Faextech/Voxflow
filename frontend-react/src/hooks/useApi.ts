import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { AxiosRequestConfig } from 'axios'

export function useGet<T>(key: string[], url: string, config?: AxiosRequestConfig, options?: object) {
  return useQuery<T>({
    queryKey: key,
    queryFn:  () => api.get<T>(url, config).then(r => r.data),
    ...options,
  })
}

export function useMut<TData = unknown, TVar = unknown>(
  method: 'post' | 'put' | 'patch' | 'delete',
  url: string | ((vars: TVar) => string),
  invalidates?: string[][],
) {
  const qc = useQueryClient()
  return useMutation<TData, Error, TVar>({
    mutationFn: (vars: TVar) => {
      const u = typeof url === 'function' ? url(vars) : url
      return api[method]<TData>(u, vars as object).then(r => r.data)
    },
    onSuccess: () => {
      invalidates?.forEach(k => qc.invalidateQueries({ queryKey: k }))
    },
  })
}
