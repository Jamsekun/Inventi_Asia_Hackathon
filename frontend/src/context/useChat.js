import { useContext } from "react";
import ChatContext from "./ChatContext";

export function useChat() {
  return useContext(ChatContext);
}
