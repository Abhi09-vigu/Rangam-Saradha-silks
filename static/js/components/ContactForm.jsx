import React, { useState } from 'react';
import axios from 'axios';

const ContactForm = () => {
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        subject: '',
        message: ''
    });

    const [errors, setErrors] = useState({});
    const [submitting, setSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData((prev) => ({
            ...prev,
            [name]: value
        }));
        if (errors[name]) {
            setErrors((prev) => ({ ...prev, [name]: null }));
        }
    };

    const validate = () => {
        const newErrors = {};
        if (!formData.name || !formData.name.trim()) {
            newErrors.name = 'Name is required.';
        }
        if (!formData.email || !formData.email.trim()) {
            newErrors.email = 'Valid email is required.';
        } else {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(formData.email.trim())) {
                newErrors.email = 'Valid email is required.';
            }
        }
        if (!formData.subject || !formData.subject.trim()) {
            newErrors.subject = 'Subject is required.';
        }
        if (!formData.message || !formData.message.trim()) {
            newErrors.message = 'Message is required.';
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSuccessMessage('');
        setErrorMessage('');

        if (!validate()) {
            return;
        }

        setSubmitting(true);

        try {
            const getCookie = (name) => {
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            };

            const csrfToken = getCookie('csrftoken') || (window.CSRF_TOKEN ? window.CSRF_TOKEN : '');

            const response = await axios.post('/api/contact/', formData, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            if (response.status === 201 || (response.data && response.data.success)) {
                setSuccessMessage(
                    response.data.message || 'Thank you for contacting us. We will get back to you shortly.'
                );
                setFormData({
                    name: '',
                    email: '',
                    subject: '',
                    message: ''
                });
                setErrors({});
            } else {
                setErrorMessage(response.data.message || 'Failed to send message. Please try again.');
            }
        } catch (error) {
            if (error.response && error.response.data) {
                const apiData = error.response.data;
                if (apiData.message) {
                    setErrorMessage(apiData.message);
                } else {
                    setErrorMessage('Submission failed. Please check your inputs and try again.');
                }
                if (apiData.errors) {
                    setErrors(apiData.errors);
                }
            } else {
                setErrorMessage('Error sending email or connecting to server. Please try again later.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="card border-0 shadow-lg p-4 p-md-5" style={{ borderRadius: '24px' }}>
            <h3 className="font-heading mb-4 text-center">Send Us a Message</h3>

            {successMessage && (
                <div className="alert alert-success border-0 shadow-sm mb-4" role="alert">
                    <i className="bi bi-check-circle-fill me-2"></i>
                    {successMessage}
                </div>
            )}

            {errorMessage && (
                <div className="alert alert-danger border-0 shadow-sm mb-4" role="alert">
                    <i className="bi bi-exclamation-triangle-fill me-2"></i>
                    {errorMessage}
                </div>
            )}

            <form onSubmit={handleSubmit} noValidate>
                <div className="mb-3">
                    <label htmlFor="name" className="form-label text-muted">
                        Your Name <span className="text-danger">*</span>
                    </label>
                    <input
                        type="text"
                        name="name"
                        id="name"
                        className={`form-control px-3 py-2 ${errors.name ? 'is-invalid' : ''}`}
                        placeholder="John Doe"
                        value={formData.name}
                        onChange={handleChange}
                        disabled={submitting}
                    />
                    {errors.name && <div className="invalid-feedback">{errors.name}</div>}
                </div>

                <div className="mb-3">
                    <label htmlFor="email" className="form-label text-muted">
                        Email Address <span className="text-danger">*</span>
                    </label>
                    <input
                        type="email"
                        name="email"
                        id="email"
                        className={`form-control px-3 py-2 ${errors.email ? 'is-invalid' : ''}`}
                        placeholder="john@example.com"
                        value={formData.email}
                        onChange={handleChange}
                        disabled={submitting}
                    />
                    {errors.email && <div className="invalid-feedback">{errors.email}</div>}
                </div>

                <div className="mb-3">
                    <label htmlFor="subject" className="form-label text-muted">
                        Subject <span className="text-danger">*</span>
                    </label>
                    <input
                        type="text"
                        name="subject"
                        id="subject"
                        className={`form-control px-3 py-2 ${errors.subject ? 'is-invalid' : ''}`}
                        placeholder="Inquiry about Kanchipuram Sarees"
                        value={formData.subject}
                        onChange={handleChange}
                        disabled={submitting}
                    />
                    {errors.subject && <div className="invalid-feedback">{errors.subject}</div>}
                </div>

                <div className="mb-4">
                    <label htmlFor="message" className="form-label text-muted">
                        Your Message <span className="text-danger">*</span>
                    </label>
                    <textarea
                        name="message"
                        id="message"
                        rows="5"
                        className={`form-control px-3 py-2 ${errors.message ? 'is-invalid' : ''}`}
                        placeholder="Write your message here..."
                        value={formData.message}
                        onChange={handleChange}
                        disabled={submitting}
                    ></textarea>
                    {errors.message && <div className="invalid-feedback">{errors.message}</div>}
                </div>

                <div className="text-center">
                    <button
                        type="submit"
                        className="btn btn-primary w-100 py-2.5"
                        disabled={submitting}
                    >
                        {submitting ? (
                            <>
                                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                Sending Message...
                            </>
                        ) : (
                            'Send Message'
                        )}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default ContactForm;
