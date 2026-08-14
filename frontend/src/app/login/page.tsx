import { auth } from "@/auth";
import { callbackUrlSeguro } from "@/lib/callback-url";
import LoginForm from "./LoginForm";
import { redirect } from "next/navigation";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>;
}) {
  const params = await searchParams;
  const callbackUrl = callbackUrlSeguro(params.callbackUrl);
  const session = await auth();
  if (session?.user) {
    redirect(callbackUrl);
  }
  return <LoginForm callbackUrl={callbackUrl} />;
}
