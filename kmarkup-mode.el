;;; kmarkup-mode.el --- Major mode for kmarkup files -*- lexical-binding: t; -*-

;; Author: Ken Schutte
;; Keywords: languages

;;; Commentary:

;; Basic major mode for kmarkup with highlighting for:
;; - tag identifiers immediately following "{"
;; - curly braces
;; - triple-backtick raw text blocks

;;; Code:

(defgroup kmarkup nil
  "Major mode for editing kmarkup."
  :group 'languages)

(defconst kmarkup-mode--font-lock-keywords
  `((,(rx "#" (* nonl)) . font-lock-comment-face)
    (,(rx "```" (*? anything) "```") . font-lock-string-face)
    (,(rx (group (any "{}"))) . font-lock-keyword-face)
    (,(rx "{" (group (+ (not (any " \t\r\n}`"))))) 1 font-lock-function-name-face))
  "Font-lock rules for `kmarkup-mode'.")

(define-derived-mode kmarkup-mode text-mode "kmarkup"
  "Major mode for editing kmarkup markup."
  (setq-local font-lock-defaults '(kmarkup-mode--font-lock-keywords))
  (setq-local comment-start "#")
  (setq-local comment-end ""))

(add-to-list 'auto-mode-alist '("\\.kmarkup\\'" . kmarkup-mode))
(add-to-list 'auto-mode-alist '("\\.km\\'" . kmarkup-mode))

(provide 'kmarkup-mode)

;;; kmarkup-mode.el ends here
