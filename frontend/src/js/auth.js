class Auth {
    static API_BASE_URL = (() => {
        const isLocalhost =
            window.location.protocol === "file:" ||
            window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1";

        return isLocalhost ? "http://127.0.0.1:8000/api/v1" : "/api/v1";
    })();

    /**
     * Проверяет, авторизован ли пользователь
     * @returns {boolean} - true, если пользователь авторизован
     */
    static isAuth() {
        const token = localStorage.getItem("access_token");
        return !!token;
    }

    /**
     * Получает токен авторизации
     * @returns {string|null} - токен или null, если не найден
     */
    static getAuthToken() {
        return localStorage.getItem("access_token");
    }

    /**
     * Получает тип токена
     * @returns {string} - тип токена (обычно "bearer")
     */
    static getTokenType() {
        return localStorage.getItem("token_type") || "bearer";
    }

    /**
     * Сохраняет токен в localStorage
     * @param {string} token - токен доступа
     * @param {string} type - тип токена
     */
    static setAuthToken(token, type = "bearer") {
        localStorage.setItem("access_token", token);
        localStorage.setItem("token_type", type);
    }

    /**
     * Удаляет токен из localStorage
     */
    static removeAuthToken() {
        localStorage.removeItem("access_token");
        localStorage.removeItem("token_type");
    }

    /**
     * Получает заголовки для авторизованных запросов
     * @returns {Object} - объект с заголовками
     */
    static getAuthHeaders() {
        const token = Auth.getAuthToken();
        const tokenType = Auth.getTokenType();

        if (!token) {
            return {};
        }

        return {
            "Authorization": `${tokenType} ${token}`,
            "Content-Type": "application/json"
        };
    }

    /**
     * Отправляет запрос с авторизацией
     * @param {string} url - URL для запроса
     * @param {Object} options - опции запроса
     * @returns {Promise<Response>} - ответ от сервера
     */
    static async authenticatedFetch(url, options = {}) {
        const headers = options.headers || {};
        const authHeaders = Auth.getAuthHeaders();

        // Объединяем заголовки, сохраняя кастомные
        const finalHeaders = { ...authHeaders, ...headers };

        const finalOptions = {
            ...options,
            headers: finalHeaders
        };

        const response = await fetch(url, finalOptions);

        // Если токен недействителен, перенаправляем на страницу входа
        if (response.status === 401) {
            Auth.removeAuthToken();
            // window.location.href = "./login.html";
            throw new Error("Не авторизован");
        }

        return response;
    }

    /**
     * Вход пользователя
     * @param {string} login - логин пользователя
     * @param {string} password - пароль
     * @returns {Promise<Object>} - данные ответа
     */
    static async login(login, password) {
        const response = await fetch(`${Auth.API_BASE_URL}/users/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                login,
                password,
            }),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Ошибка авторизации");
        }

        if (data.access_token) {
            Auth.setAuthToken(data.access_token, data.token_type);
        }

        return data;
    }

    /**
     * Регистрация пользователя
     * @param {Object} userData - данные пользователя
     * @param {string} userData.name - имя пользователя
     * @param {string} userData.phone - телефон
     * @param {string} userData.password - пароль
     * @returns {Promise<Object>} - данные ответа
     */
    static async register(userData) {
        const response = await fetch(`${Auth.API_BASE_URL}/users/register`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(userData),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Ошибка регистрации");
        }

        return data;
    }

    /**
     * Получение данных текущего пользователя
     * @returns {Promise<Object>} - данные пользователя
     */
    static async getCurrentUser() {
        const response = await Auth.authenticatedFetch(`${Auth.API_BASE_URL}/users/me`);

        if (response.ok) {
            const user = await response.json();
            return user;
        } else {
            console.error('Ошибка получения данных пользователя');
            return null;
        }
    }

    /**
     * Выход из системы
     */
    static logout() {
        Auth.removeAuthToken();
        window.location.href = "./login.html";
    }

    /**
     * Проверяет и обновляет состояние авторизации при загрузке страницы
     */
    static checkAuthStatus() {
        if (!Auth.isAuth()) {
            // Если мы не на странице входа/регистрации, перенаправляем на вход
            const currentPath = window.location.pathname;
            const isAuthPage = currentPath.includes('login.html') || currentPath.includes('register.html');

            if (!isAuthPage) {
                window.location.href = "./login.html";
                return false;
            }
        }

        return true;
    }
}

export default Auth;
