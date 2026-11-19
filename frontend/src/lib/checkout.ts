import { post } from "./api";

type CheckoutResp = { payment: { id: string }; checkout: { method: "redirect" | "form_post"; url: string; fields: Record<string, string> } };

/** Starts a checkout and hands the browser to the payment provider (or the labelled sandbox page). */
export async function startCheckout(purpose: string, referenceId: string) {
  const r = await post<CheckoutResp>("/payments/checkout", { purpose, reference_id: referenceId });
  if (r.checkout.method === "form_post") {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = r.checkout.url;
    for (const [k, v] of Object.entries(r.checkout.fields)) {
      const i = document.createElement("input");
      i.type = "hidden";
      i.name = k;
      i.value = v;
      form.appendChild(i);
    }
    document.body.appendChild(form);
    form.submit();
  } else {
    const url = new URL(r.checkout.url, window.location.origin); // works for absolute and relative links
    window.location.href = url.pathname + url.search; // same-origin sandbox page
  }
}
