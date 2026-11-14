// Yetkinlik profili okuması (yalnız GET): API'nin "profil yok = 404" sözleşmesi değişmez,
// ama tarayıcı her 404 yanıtını konsola ağ hatası olarak yazar ve "henüz tanımlanmadı"
// olağan bir durumdur. Bu uç, aynı-origin proxy'nin GET'ini (token yenileme dahil) çağırır
// ve yalnız 404'ü `200 null`a çevirir; diğer her yanıt olduğu gibi geçer. Yazma (POST)
// genel proxy'den (`/api/v1/capability-profile`) yapılmaya devam eder.

import { NextRequest } from "next/server";

import { GET as proxyGet } from "../v1/[...path]/route";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest): Promise<Response> {
  const response = await proxyGet(request, {
    params: Promise.resolve({ path: ["capability-profile"] }),
  });
  if (response.status !== 404) return response;
  const headers = new Headers({ "content-type": "application/json" });
  // Proxy token'ı yenilediyse yeni cookie'ler kaybolmasın.
  for (const cookie of response.headers.getSetCookie()) headers.append("set-cookie", cookie);
  return new Response("null", { status: 200, headers });
}
