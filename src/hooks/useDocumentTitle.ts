import { useEffect } from 'react';

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · Sahkar Saathi` : 'Sahkar Saathi';
  }, [title]);
}
