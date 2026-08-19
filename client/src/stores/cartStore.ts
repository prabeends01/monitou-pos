import { create } from "zustand";

import { addScan, removeLine, setQty, subtotal } from "../cart";
import type { CartLine } from "../cart";
import type { BarcodeScanResult } from "../types";

interface CartState {
  lines: CartLine[];
  addScan: (row: BarcodeScanResult) => void;
  setQty: (barcodeId: string, qtyBaseUnits: number) => void;
  removeLine: (barcodeId: string) => void;
  clear: () => void;
  subtotal: () => number;
}

export const useCartStore = create<CartState>((set, get) => ({
  lines: [],
  addScan: (row) => set((state) => ({ lines: addScan(state.lines, row) })),
  setQty: (barcodeId, qtyBaseUnits) => set((state) => ({ lines: setQty(state.lines, barcodeId, qtyBaseUnits) })),
  removeLine: (barcodeId) => set((state) => ({ lines: removeLine(state.lines, barcodeId) })),
  clear: () => set({ lines: [] }),
  subtotal: () => subtotal(get().lines),
}));
