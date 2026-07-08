const form = document.getElementById("chat-form");
const input = document.getElementById("message-input");
const messages = document.getElementById("messages");
const sessionLabel = document.getElementById("session-label");
const sessionStorageKey = "vega_demo_session_id";

let sessionId = localStorage.getItem(sessionStorageKey);

if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem(sessionStorageKey, sessionId);
}

function updateSessionLabel() {
  sessionLabel.textContent = `Session: ${sessionId.slice(0, 8)}`;
}

updateSessionLabel();

function appendMessage(role, text, className) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${className}`;

  const roleNode = document.createElement("div");
  roleNode.className = "role";
  roleNode.textContent = role;

  const contentNode = document.createElement("div");
  contentNode.className = "content";
  contentNode.textContent = text;

  wrapper.append(roleNode, contentNode);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;

  return wrapper;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const text = input.value.trim();
  if (!text) {
    return;
  }

  appendMessage("You", text, "user");
  input.value = "";
  input.disabled = true;

  const thinking = appendMessage("VEGA", "VEGA is thinking...", "assistant status");

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    });

    if (!response.ok) {
      throw new Error(`Server returned ${response.status}`);
    }

    const data = await response.json();
    if (data.session_id) {
      sessionId = data.session_id;
      localStorage.setItem(sessionStorageKey, sessionId);
      updateSessionLabel();
    }

    thinking.querySelector(".content").textContent = data.reply || "VEGA returned an empty reply.";
    thinking.classList.remove("status");
  } catch (error) {
    thinking.querySelector(".content").textContent =
      "Connection error. Check that the VEGA web demo server is running.";
    thinking.classList.add("error");
  } finally {
    input.disabled = false;
    input.focus();
  }
});
